"""M1 数据验证脚本：校验入库数据的完整性与一致性。

检查项：
1. 企业档案数量 ≥ 100（202 家种子全建档）
2. 有证据档案 ≥ 40（M1 实测 43；M2 经 猎聘/UGC 追到 100+）
3. 等级在 1~6，置信度在 0~1
4. L1/L2（双休）企业中 ≥10 家有 ≥2 条证据交叉验证
5. 输出等级分布与抽样明细（人工抽检用）
"""

import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import create_engine, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Company, Evidence, LEVEL_NAMES, Base

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "shuangxiugou.db"

failures = []


def check(cond: bool, msg: str):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        failures.append(msg)


def main():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        total = conn.execute(select(func.count(Company.id))).scalar()
        with_evidence = conn.execute(
            select(func.count(func.distinct(Evidence.company_id)))
        ).scalar()
        levels = dict(conn.execute(
            select(Company.level, func.count(Company.id)).group_by(Company.level)
        ).all())
        bad_levels = conn.execute(
            select(Company.id).where(~Company.level.between(1, 6))
        ).all()
        bad_conf = conn.execute(
            select(Company.id).where(~Company.confidence.between(0, 1))
        ).all()

    print(f"[M1 验证] 企业档案: {total}，有证据: {with_evidence}")
    print(f"[M1 验证] 等级分布: {levels}")

    check(total >= 100, f"企业档案 ≥ 100（实际 {total}）")
    check(with_evidence >= 40, f"有证据档案 ≥ 40（实际 {with_evidence}）")
    check(not bad_levels, "无越界等级（1~6）")
    check(not bad_conf, "置信度均在 0~1")

    with engine.connect() as conn:
        rows = conn.execute(
            select(Company.name, Company.level, Company.confidence,
                   func.count(Evidence.id))
            .join(Evidence, Evidence.company_id == Company.id)
            .group_by(Company.id)
            .order_by(Company.level, Company.confidence.desc())
        ).all()
        sources = dict(conn.execute(
            select(Evidence.source_type, func.count(Evidence.id))
            .group_by(Evidence.source_type)
        ).all())

    dual_sources = 0
    for name, lv, conf, n in rows:
        if lv in (1, 2) and n >= 2:
            dual_sources += 1
    print(f"[M1 验证] 证据来源分布: {sources}")
    check(dual_sources >= 10,
          f"L1/L2 中 ≥2 条证据交叉验证的企业数 ≥ 10（实际 {dual_sources}）")

    print("\n[抽样明细]（人工抽检用，L1/L2 前置）")
    for name, lv, conf, n in sorted(rows, key=lambda r: (r[1], -r[2]))[:25]:
        print(f"  L{lv} {conf:.2f} {n:2d}条  {name}")

    if failures:
        print(f"\n[M1 验证] FAILED: {len(failures)} 项未通过")
        sys.exit(1)
    print("\n[M1 验证] ALL PASS")


if __name__ == "__main__":
    main()