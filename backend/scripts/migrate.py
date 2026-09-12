"""轻量 schema/数据迁移机制（alembic 的 SQLite 开发期替代）。

- 每个迁移 = (版本号, 名称, 幂等执行函数)
- 已应用版本记录在 schema_version 表，重复运行自动跳过
- 生产切 PostgreSQL 时可平移到 alembic（迁移函数逻辑可复用）

用法: .venv/bin/python scripts/migrate.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.models import Base
from app.db.session import engine
from app.services.levels import weight_for


def _ensure_version_table(e: Engine):
    with e.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"))
        conn.commit()


def _applied_versions(e: Engine) -> set:
    with e.connect() as conn:
        return {row[0] for row in conn.execute(text("SELECT version FROM schema_version"))}


def _mark_applied(e: Engine, version: int, name: str):
    with e.connect() as conn:
        conn.execute(text(
            "INSERT INTO schema_version (version, name, applied_at) "
            f"VALUES ({version}, '{name}', '{datetime.utcnow().isoformat()}')"))
        conn.commit()


def migration_0001_weight_snapshot(e: Engine):
    """Evidence.weight 改为「来源权重快照」语义：按 source_type 回填，并重算全部企业等级。"""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db.models import Company, Evidence
    from app.services.levels import recalc_company

    with Session(e) as db:
        for ev in db.scalars(select(Evidence)):
            ev.weight = weight_for(ev.source_type or "")
        db.commit()
        for c in db.scalars(select(Company)):
            recalc_company(c, db)
        db.commit()


MIGRATIONS = [
    (1, "evidence weight snapshot backfill", migration_0001_weight_snapshot),
]


def run(e: Engine = engine):
    _ensure_version_table(e)
    applied = _applied_versions(e)
    for version, name, fn in MIGRATIONS:
        if version in applied:
            print(f"  [skip] {version:04d} {name}（已应用）")
            continue
        fn(e)
        _mark_applied(e, version, name)
        print(f"  [ ok ] {version:04d} {name}")
    print("迁移完成")


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    run()
    print("下一步: crawler/verify.py 校验数据一致性")