"""数据一致性校验：DB ↔ 开源数据包（data/*.json）↔ 本地版 bundle（web/local/dist/data.js）。

发布前 / CI 使用：任何不一致退出码非 0。

用法: .venv/bin/python scripts/check_consistency.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, Job, WHITELIST_LEVELS
from app.db.session import engine

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BUNDLE = ROOT / "web" / "local" / "dist" / "data.js"

failures = []


def check(cond: bool, msg: str):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        failures.append(msg)


def load_public():
    return json.loads((DATA / "companies.json").read_text(encoding="utf-8"))


def load_bundle():
    if not BUNDLE.exists():
        return None
    raw = BUNDLE.read_text(encoding="utf-8")
    m = re.search(r"window\.SXG_DATA = (\{.*\});", raw, re.S)
    return json.loads(m.group(1)) if m else None


def main():
    public = load_public()
    jobs = json.loads((DATA / "jobs.json").read_text(encoding="utf-8"))

    with Session(engine) as db:
        db_whitelist = db.scalars(
            select(Company).where(Company.level.in_(WHITELIST_LEVELS))).all()
        db_jobs = db.scalars(
            select(Job).join(Company, Company.id == Job.company_id)
            .where(Job.active.is_(True), Company.level.in_(WHITELIST_LEVELS))).all()

    print(f"[一致性] DB 白名单 {len(db_whitelist)} | companies.json {public['count']} "
          f"| DB 在招岗位 {len(db_jobs)} | jobs.json {jobs['count']}")

    # 1) 白名单数量一致
    check(public["count"] == len(db_whitelist), "companies.json 与 DB 白名单数量一致")
    # 2) 数据包等级只含 L1/L2
    check({c["level"] for c in public["companies"]} <= set(WHITELIST_LEVELS),
          "companies.json 只含白名单等级")
    # 3) 岗位数量一致
    check(jobs["count"] == len(db_jobs), "jobs.json 与 DB 白名单在招岗位数量一致")
    # 4) 岗位企业都在公开白名单内
    public_names = {c["name"] for c in public["companies"]}
    orphan = [j["company_name"] for j in jobs["jobs"] if j["company_name"] not in public_names]
    check(not orphan, f"jobs.json 岗位均来自公开白名单企业（异常 {orphan[:3]}）")

    # 5) 本地 bundle 与数据包一致（dist 存在时才校验）
    bundle = load_bundle()
    if bundle is None:
        print("  [skip] web/local/dist 不存在（未构建本地包）")
    else:
        check(len(bundle["companies"]) == public["count"], "bundle 企业数与 companies.json 一致")
        check(len(bundle["jobs"]) == jobs["count"], "bundle 岗位数与 jobs.json 一致")

    if failures:
        print(f"\n[一致性] FAILED: {len(failures)} 项")
        sys.exit(1)
    print("\n[一致性] ALL PASS")


if __name__ == "__main__":
    main()