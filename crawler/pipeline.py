"""M1 主管线：读取种子企业 → 多源采集 → 打分 → 聚合 → 写入 SQLite。

用法:
    python pipeline.py --limit 10        # 只跑前 10 家（验证用）
    python pipeline.py                   # 全量 202 家（约 60~90 分钟）
    python pipeline.py --json out.json   # 不写库，输出证据 JSON（联调用）
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Base, Company, Evidence
from app.services.levels import aggregate, weight_for

from sources.bing_snippet import BingSnippetSource
from sources.zhaopin import ZhaopinSource

DATA_DIR = Path(__file__).resolve().parents[1]
SEED_CSV = DATA_DIR / "data" / "companies" / "seed.csv"
DB_PATH = DATA_DIR / "data" / "shuangxiugou.db"


def load_seed_csv() -> list[dict]:
    with open(SEED_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dedup_evidence(evs: list) -> list:
    seen = set()
    out = []
    for e in evs:
        key = (e.company_key, e.url, "-".join(sorted(e.keywords)))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def write_to_db(engine, companies: list[dict], all_evidences: list):
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for c in companies:
            evs = [e for e in all_evidences if e.company_key == c["key"]]
            company_row = db.scalar(select(Company).where(Company.name == c["full_name"]))
            if not company_row:
                company_row = Company(
                    name=c["full_name"],
                    level=6, confidence=0.0,
                    next_recheck_at=None, updated_at=sa.func.now(),
                )
                db.add(company_row)
                db.flush()
            if evs:
                docs = [{
                    "raw_score": e.raw_score,
                    "weight": 1.0,
                    "collected_at": e.collected_at,
                    "source_type": e.source_type,
                } for e in evs]
                level, confidence = aggregate(docs)
                company_row.level = level
                company_row.confidence = confidence
            for e in evs:
                existing = db.scalar(select(Evidence).where(
                    Evidence.company_id == company_row.id,
                    Evidence.url == e.url,
                ))
                if existing:
                    continue
                db.add(Evidence(
                    company_id=company_row.id,
                    source_type=e.source_type,
                    url=e.url,
                    keywords=",".join(e.keywords),
                    raw_score=e.raw_score,
                    weight=weight_for(e.source_type),
                    collected_at=e.collected_at,
                    reviewed=False,
                ))
        db.commit()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 家")
    ap.add_argument("--json", help="输出原始证据到文件（不写库）")
    ap.add_argument("--names", help="逗号分隔的指定企业 key（跳过种子文件读取）")
    ap.add_argument("--politeness", type=float, default=1.5,
                    help="公司间限速秒数（默认 1.5s）")
    args = ap.parse_args()

    if args.names:
        seed_index = {r["key"]: r for r in load_seed_csv()}
        companies = []
        for k in [x.strip() for x in args.names.split(",") if x.strip()]:
            if k in seed_index:
                companies.append(seed_index[k])
            else:
                companies.append({"key": k, "full_name": k, "category": ""})
    else:
        companies = load_seed_csv()
        if args.limit:
            companies = companies[: args.limit]

    print(f"[M1] 开始采集 {len(companies)} 家企业（共享浏览器模式）")
    all_evs = []
    bing = BingSnippetSource()
    zhaopin = ZhaopinSource(city_id="530")
    loop = asyncio.get_event_loop()
    t0 = loop.time()
    async with zhaopin.launch_shared():
        for i, c in enumerate(companies, 1):
            evs = []
            try:
                evs += await zhaopin.fetch(c["key"])
            except Exception as e:
                print(f"  [zhaopin 失败] {c['key']}: {type(e).__name__}: {str(e)[:100]}")
            try:
                evs += await bing.fetch(c["key"])
            except Exception as e:
                print(f"  [bing 失败] {c['key']}: {type(e).__name__}: {str(e)[:100]}")
            evs = dedup_evidence(evs)
            all_evs += evs
            scores = sorted({e.raw_score for e in evs}, reverse=True)
            print(f"[{i}/{len(companies)}] {c['key']}: {len(evs)} 条证据 "
                  f"打分范围 {scores[:3] if scores else '-'} 耗时{loop.time()-t0:.0f}s")
            t0 = loop.time()
            if i < len(companies):
                await asyncio.sleep(args.politeness)

    if args.json:
        json.dump([{
            "company_key": e.company_key, "company_raw": e.company_raw,
            "source_type": e.source_type, "url": e.url, "title": e.title,
            "snippet": e.snippet, "keywords": e.keywords, "raw_score": e.raw_score,
            "collected_at": e.collected_at.isoformat(),
        } for e in all_evs], open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[M1] 已输出 {len(all_evs)} 条证据到 {args.json}")
        return

    engine = create_engine(f"sqlite:///{DB_PATH}")
    write_to_db(engine, companies, all_evs)
    print(f"[M1] 完成，共 {len(all_evs)} 条证据写入 {DB_PATH}")
    print(f"[M1] 下一步: python verify.py")


if __name__ == "__main__":
    asyncio.run(main())