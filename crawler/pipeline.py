"""M1 主管线：读取种子企业 → 多源采集 → 打分 → 聚合 → 写入 SQLite。

用法:
    python pipeline.py --limit 10        # 只跑前 10 家（验证用）
    python pipeline.py                   # 全量（1000+ 家，建议分批或本地夜间跑）
    python pipeline.py --chunk 2/4       # 哈希分片（CI 周更）
    python pipeline.py --stale-days 28   # 本地增量：只采证据过期/缺失的企业
    python pipeline.py --json out.json   # 不写库，输出证据 JSON（联调用）
"""

import argparse
import asyncio
import csv
import hashlib
import json
import sys
from contextlib import nullcontext
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Base, Company, Evidence
from app.services.levels import aggregate, weight_for

from health import new_health, record, write_report
from sources.registry import load_config, make_evidence_sources

DATA_DIR = Path(__file__).resolve().parents[1]
SEED_CSV = DATA_DIR / "data" / "companies" / "seed.csv"
DB_PATH = DATA_DIR / "data" / "shuangxiugou.db"
COMPANIES_JSON = DATA_DIR / "data" / "companies.json"


def load_seed_csv() -> list[dict]:
    with open(SEED_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_whitelist_json() -> dict:
    """读取公开白名单制品（data/companies.json），不存在时返回空。"""
    if not COMPANIES_JSON.exists():
        return {}
    with open(COMPANIES_JSON, encoding="utf-8") as f:
        return json.load(f)


def _parse_date(raw) -> date:
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return date.today()


def rehydrate_whitelist(engine, payload: dict) -> int:
    """把公开白名单证据回灌进 DB（CI 从空仓库开跑时的状态恢复）。

    CI 每次 checkout 都是空 DB：不回灌则分片周更只反映当周分片，
    companies.json 会震荡甚至缩水。只回灌公开制品（L1/L2）证据，
    全量评级仍只在本地生成（保守数据策略）。
    """
    companies = payload.get("companies") or []
    if not companies:
        return 0
    Base.metadata.create_all(engine)
    added = 0
    with Session(engine) as db:
        for c in companies:
            name = c.get("name")
            if not name:
                continue
            row = db.scalar(select(Company).where(Company.name == name))
            if not row:
                row = Company(name=name, level=c.get("level", 6),
                              confidence=c.get("confidence", 0.0))
                db.add(row)
                db.flush()
            elif not c.get("evidences"):
                continue  # 无证据可回灌：不覆盖本地已算出的等级
            for e in c.get("evidences") or []:
                url = e.get("url") or ""
                if url and db.scalar(select(Evidence).where(
                        Evidence.company_id == row.id, Evidence.url == url)):
                    continue
                db.add(Evidence(
                    company_id=row.id,
                    source_type=e.get("source_type", "review"),
                    url=url,
                    keywords=",".join(e.get("keywords") or []),
                    raw_score=e.get("raw_score", 0.0),
                    weight=e.get("weight") or weight_for(e.get("source_type", "review")),
                    collected_at=_parse_date(e.get("collected_at")),
                    reviewed=False,
                ))
                added += 1
        db.commit()
    return added


def split_whitelist(companies: list[dict], whitelist_names: set) -> tuple[list, list]:
    """拆成（白名单, 其余）：白名单每周全采，其余走分片/新鲜度过筛。"""
    base = [c for c in companies if c["full_name"] in whitelist_names]
    rest = [c for c in companies if c["full_name"] not in whitelist_names]
    return base, rest


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


def chunk_companies(companies: list[dict], spec: str) -> list[dict]:
    """按 key 哈希把企业池切成 N 片，取第 K 片（无状态周更分片）。

    企业池 1000+ 后 CI 单次跑不完全量：`--chunk K/N` 按确定性哈希分片，
    每周取一片（如 `--chunk $(周数%4+1)/4`），4 周覆盖全池。
    """
    k, n = (int(x) for x in spec.split("/"))
    if not (1 <= k <= n):
        raise ValueError(f"--chunk 需形如 K/N 且 1<=K<=N，收到 {spec}")
    out = [c for c in companies
           if int(hashlib.md5(c["key"].encode("utf-8")).hexdigest(), 16) % n == k - 1]
    print(f"[M1] 分片 {k}/{n}：本轮采集 {len(out)} 家（池子 {len(companies)} 家）")
    return out


def filter_stale(companies: list[dict], stale_days: int) -> list[dict]:
    """周更分片：只保留「无证据」或「最近证据早于 stale_days」的企业。

    企业池扩编到 1000+ 后，全量采集超出 CI 单次预算；按新鲜度分片后
    每周只重采 1/N，保证时效同时控制时长（--stale-days 0 关闭过滤）。
    """
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(engine)
    cutoff = date.today() - timedelta(days=stale_days)
    with Session(engine) as db:
        rows = db.execute(
            select(Company.name, sa.func.max(Evidence.collected_at))
            .join(Evidence, Evidence.company_id == Company.id)
            .group_by(Company.id)
        ).all()
    latest = {name: dt for name, dt in rows if dt is not None}
    fresh, stale = [], []
    for c in companies:
        dt = latest.get(c["full_name"])
        (stale if dt is None or dt < cutoff else fresh).append(c)
    print(f"[M1] 新鲜度分片（--stale-days {stale_days}）："
          f"本轮采集 {len(stale)} 家，跳过 {len(fresh)} 家")
    return stale


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
            if evs:
                # 聚合以 DB 全量证据为准（含回灌的历史证据），
                # 否则增量/分片采集会只按本轮证据重算等级
                db.flush()
                docs = [{
                    "raw_score": x.raw_score,
                    "weight": x.weight,
                    "collected_at": x.collected_at,
                    "source_type": x.source_type,
                } for x in db.scalars(select(Evidence).where(
                    Evidence.company_id == company_row.id)).all()]
                level, confidence = aggregate(docs)
                company_row.level = level
                company_row.confidence = confidence
        db.commit()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 家")
    ap.add_argument("--json", help="输出原始证据到文件（不写库）")
    ap.add_argument("--names", help="逗号分隔的指定企业 key（跳过种子文件读取）")
    ap.add_argument("--chunk", help="哈希分片 K/N（CI 周更用，如 2/4）")
    ap.add_argument("--stale-days", type=int, default=0,
                    help="只采集证据过期/缺失的企业（0=全量，本地增量建议 28）")
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

        # 状态恢复 + 白名单每周全采（CI 从空仓库开跑，不回灌会导致白名单震荡）
        wl_payload = load_whitelist_json()
        whitelist_names = {c["name"] for c in wl_payload.get("companies", [])}
        base, companies = split_whitelist(companies, whitelist_names)
        if base:
            print(f"[M1] 白名单每轮全采 {len(base)} 家（公开制品状态回灌）")

        if args.chunk:
            engine = create_engine(f"sqlite:///{DB_PATH}")
            added = 0 if args.json else rehydrate_whitelist(engine, wl_payload)
            if added:
                print(f"[M1] 已回灌白名单历史证据 {added} 条")
            companies = base + chunk_companies(companies, args.chunk)
        elif args.stale_days > 0:
            companies = base + filter_stale(companies, args.stale_days)

    print(f"[M1] 开始采集 {len(companies)} 家企业（共享浏览器 + 注册表源）")
    all_evs = []
    cfg = load_config()
    sources = make_evidence_sources(cfg)
    print(f"[M1] 启用证据源: {[name for name, _ in sources]}")
    health = new_health()
    loop = asyncio.get_event_loop()
    t0 = loop.time()

    # 需要浏览器的源（智联）共享同一浏览器实例；无浏览器源时用空上下文
    browser_owner = next((s for _, s in sources if hasattr(s, "launch_shared")), None)
    if browser_owner is not None:
        ctx = browser_owner.launch_shared()
    else:
        ctx = nullcontext()

    async with ctx:
        for i, c in enumerate(companies, 1):
            evs = []
            for name, src in sources:
                try:
                    got = await src.fetch(c["key"])
                    evs += got
                    record(health, name, ok=True, items=len(got))
                except Exception as e:
                    record(health, name, ok=False)
                    print(f"  [{name} 失败] {c['key']}: {type(e).__name__}: {str(e)[:100]}")
            evs = dedup_evidence(evs)
            all_evs += evs
            scores = sorted({e.raw_score for e in evs}, reverse=True)
            print(f"[{i}/{len(companies)}] {c['key']}: {len(evs)} 条证据 "
                  f"打分范围 {scores[:3] if scores else '-'} 耗时{loop.time()-t0:.0f}s")
            t0 = loop.time()
            if i < len(companies):
                await asyncio.sleep(args.politeness)

    health_md = DATA_DIR / "data" / "source_health.md"
    health_json = DATA_DIR / "data" / "local" / "source_health.json"
    write_report(health, health_md, health_json)
    print(f"[M1] 源健康报告: {health_md}")

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