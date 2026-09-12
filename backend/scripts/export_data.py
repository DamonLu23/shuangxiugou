"""数据制品导出：SQLite 中间库 → 开源数据包（data/ 下的 JSON/CSV 制品）。

制品（提交进 git，用户 pull 即用）：
- data/companies.json   白名单企业档案（对外只含 L1/L2；全量另存 data/companies_all.json）
- data/evidences.json   证据明细（链接+关键词+日期+权重，无正文）
- data/jobs.json        岗位数据快照（白名单企业岗位）
- data/goods.csv        好物目录（由社区 PR 维护，导出不覆盖）

用法: .venv/bin/python scripts/export_data.py
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.models import Company, Evidence, Job
from app.db.session import engine

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

EXPORTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _company_dict(c: Company, evidences: list[Evidence]) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "level": c.level,
        "confidence": round(c.confidence, 3),
        "disputed": bool(c.disputed),
        "updated_at": c.updated_at.strftime("%Y-%m-%d") if c.updated_at else None,
        "evidence_count": len(evidences),
        "evidences": [{
            "source_type": e.source_type,
            "url": e.url,
            "keywords": (e.keywords or "").split(","),
            "raw_score": e.raw_score,
            "weight": e.weight,
            "collected_at": str(e.collected_at),
        } for e in evidences],
    }


def export_companies(session) -> tuple[int, int]:
    companies = session.scalars(select(Company)).all()
    all_rows, whitelist = [], []
    for c in companies:
        evs = session.scalars(
            select(Evidence).where(Evidence.company_id == c.id)
            .order_by(Evidence.raw_score.desc())
        ).all()
        row = _company_dict(c, evs)
        all_rows.append(row)
        if c.level in (1, 2):  # 白名单：对外只发布 L1/L2
            whitelist.append(row)

    payload = {
        "generated_at": EXPORTED_AT,
        "note": "等级由公开渠道证据交叉验证聚合，仅供参考；明细见 evidences 字段（来源链接）。",
        "count": len(whitelist),
        "companies": whitelist,
    }
    (DATA / "companies.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    all_payload = {
        "generated_at": EXPORTED_AT,
        "note": "全量档案（含 L3-L6）仅供本地研究/复现，不用于任何对外展示。",
        "count": len(all_rows),
        "companies": all_rows,
    }
    (DATA / "companies_all.json").write_text(
        json.dumps(all_payload, ensure_ascii=False, indent=1), encoding="utf-8")

    evidences = {
        "generated_at": EXPORTED_AT,
        "note": "仅存来源链接+关键词+日期，不存原文。",
        "count": sum(len(r["evidences"]) for r in all_rows),
        "evidences": [
            {"company_name": r["name"], **e}
            for r in all_rows for e in r["evidences"]
        ],
    }
    (DATA / "evidences.json").write_text(
        json.dumps(evidences, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(whitelist), len(all_rows)


def export_jobs(session) -> int:
    jobs = session.scalars(select(Job)).all()
    payload = {
        "generated_at": EXPORTED_AT,
        "note": "岗位快照，仅收录白名单企业（L1/L2）；岗位状态以招聘平台为准。",
        "count": len(jobs),
        "jobs": [{
            "title": j.title,
            "company_id": j.company_id,
            "company_name": j.company_name,
            "city": j.city,
            "tags": (j.tags or "").split(","),
            "url": j.url,
            "collected_at": str(j.collected_at),
        } for j in jobs],
    }
    (DATA / "jobs.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(jobs)


def ensure_goods_seed():
    goods = DATA / "goods.csv"
    if not goods.exists():
        with open(goods, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["company_name", "category", "product", "official_link", "note"])
            writer.writerow(["顺丰速运有限公司", "物流服务", "顺丰寄件", "https://www.sf-express.com", "示例行：好物目录由社区 PR 维护"])
        print("  已创建 data/goods.csv 种子文件")


def main():
    print(f"[导出] 数据制品 → {DATA}")
    from sqlalchemy.orm import Session
    with Session(engine) as session:
        wl, total = export_companies(session)
        print(f"  companies.json: 白名单 {wl} 家；companies_all.json: 全量 {total} 家")
        try:
            jobs = export_jobs(session)
            print(f"  jobs.json: {jobs} 个岗位")
        except Exception as e:
            print(f"  jobs.json: 导出失败（{type(e).__name__}），已写空快照")
            (DATA / "jobs.json").write_text(json.dumps(
                {"generated_at": EXPORTED_AT, "count": 0, "jobs": []},
                ensure_ascii=False, indent=1), encoding="utf-8")
    ensure_goods_seed()
    print("完成")


if __name__ == "__main__":
    main()