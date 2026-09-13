"""数据制品导出：SQLite 中间库 → 开源数据包（公开制品 / 本地复现报告）。

【保守数据策略】
- 公开制品（进 git，用户 pull 即用）：
  - data/companies.json   白名单企业档案（仅 L1/L2，证据内嵌可复核）
  - data/jobs.json        白名单岗位快照
  - data/goods.csv        好物目录（社区 PR 维护，导出不覆盖）
- 本地复现（--full，写入 data/local/，该目录已 gitignore，不发布）：
  - data/local/companies_all.json  全量档案（含 L3~L6，仅供自愿复现者本地查看）
  - data/local/evidences.json      全量证据明细

用法:
    .venv/bin/python scripts/export_data.py        # 公开制品
    .venv/bin/python scripts/export_data.py --full # 公开制品 + 本地全量报告
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.models import Company, Evidence, Job, WHITELIST_LEVELS
from app.db.session import engine

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
LOCAL = DATA / "local"

EXPORTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _evidence_dict(e: Evidence) -> dict:
    return {
        "source_type": e.source_type,
        "url": e.url,
        "keywords": (e.keywords or "").split(","),
        "raw_score": e.raw_score,
        "weight": e.weight,
        "collected_at": str(e.collected_at),
    }


def export_public(session) -> tuple[int, int, int]:
    """公开制品：白名单企业（含证据）+ 岗位 + goods 种子。"""
    companies = session.scalars(select(Company)).all()
    whitelist = []
    for c in companies:
        if c.level not in (1, 2):
            continue
        evs = session.scalars(
            select(Evidence).where(Evidence.company_id == c.id)
            .order_by(Evidence.raw_score.desc())
        ).all()
        whitelist.append({
            "id": c.id,
            "name": c.name,
            "level": c.level,
            "confidence": round(c.confidence, 3),
            "disputed": bool(c.disputed),
            "updated_at": c.updated_at.strftime("%Y-%m-%d") if c.updated_at else None,
            "evidence_count": len(evs),
            "evidences": [_evidence_dict(e) for e in evs],
        })

    payload = {
        "generated_at": EXPORTED_AT,
        "strategy": "保守策略：本仓库仅发布白名单（L1/L2）推荐数据，不发布任何负面评级。",
        "count": len(whitelist),
        "companies": whitelist,
    }
    (DATA / "companies.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    jobs = export_jobs(session)
    return len(whitelist), jobs


def export_jobs(session) -> int:
    """岗位导出：仅白名单企业在招岗位（未审 UGC/已下架/非白名单全部排除）。"""
    jobs = session.scalars(
        select(Job)
        .join(Company, Company.id == Job.company_id)
        .where(Job.active.is_(True), Company.level.in_(WHITELIST_LEVELS))
    ).all()
    job_payload = {
        "generated_at": EXPORTED_AT,
        "note": "岗位快照，仅收录白名单企业（L1/L2）在招岗位；岗位状态以招聘平台为准。",
        "count": len(jobs),
        "jobs": [{
            "title": j.title,
            "company_id": j.company_id,
            "company_name": j.company_name,
            "city": j.city,
            "tags": (j.tags or "").split(","),
            "salary": j.salary,
            "url": j.url,
            "collected_at": str(j.collected_at),
        } for j in jobs],
    }
    (DATA / "jobs.json").write_text(
        json.dumps(job_payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(jobs)


def export_local_full(session) -> int:
    """本地复现报告（gitignore，不入仓库）：全量档案 + 全量证据。"""
    LOCAL.mkdir(exist_ok=True)
    companies = session.scalars(select(Company)).all()
    all_rows = []
    for c in companies:
        evs = session.scalars(
            select(Evidence).where(Evidence.company_id == c.id)
            .order_by(Evidence.raw_score.desc())
        ).all()
        all_rows.append({
            "id": c.id,
            "name": c.name,
            "level": c.level,
            "confidence": round(c.confidence, 3),
            "disputed": bool(c.disputed),
            "updated_at": c.updated_at.strftime("%Y-%m-%d") if c.updated_at else None,
            "evidence_count": len(evs),
            "evidences": [_evidence_dict(e) for e in evs],
        })
    (LOCAL / "companies_all.json").write_text(json.dumps({
        "generated_at": EXPORTED_AT,
        "note": "本地复现报告：含 L3~L6 全量评级。仅用于个人研究/复现，请勿对外展示、转载、传播。",
        "count": len(all_rows),
        "companies": all_rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    (LOCAL / "evidences.json").write_text(json.dumps({
        "generated_at": EXPORTED_AT,
        "note": "全量证据明细（链接+关键词+日期，不存原文）。仅本地研究使用。",
        "count": sum(r["evidence_count"] for r in all_rows),
        "evidences": [
            {"company_name": r["name"], **e}
            for r in all_rows for e in r["evidences"]
        ],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(all_rows)


def ensure_goods_seed():
    goods = DATA / "goods.csv"
    if not goods.exists():
        with open(goods, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["company_name", "category", "product", "official_link", "note"])
            writer.writerow(["顺丰速运有限公司", "物流服务", "顺丰寄件", "https://www.sf-express.com", "示例行：好物目录由社区 PR 维护"])
        print("  已创建 data/goods.csv 种子文件")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="额外生成本地全量复现报告（data/local/）")
    args = ap.parse_args()

    print(f"[导出] 公开制品 → {DATA}")
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        wl, jobs = export_public(session)
        print(f"  companies.json: 白名单 {wl} 家；jobs.json: {jobs} 个岗位")
        if args.full:
            total = export_local_full(session)
            print(f"  data/local/companies_all.json: 全量 {total} 家（已 gitignore，不发布）")
    ensure_goods_seed()
    print("完成")


if __name__ == "__main__":
    main()