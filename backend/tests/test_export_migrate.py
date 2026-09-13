"""数据导出 / 迁移机制测试。

- export_data：公开制品只含白名单；全量报告含 L3~L6；计数正确
- migrate：幂等（重复运行跳过已应用版本）
"""

import json
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.models import Base, Company, Evidence
from app.services import levels
from datetime import date


def _temp_db_engine():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    return e


def _seed(engine):
    with Session(engine) as s:
        white = Company(name="白名单公司", level=1, confidence=0.9)
        dual = Company(name="双休公司", level=2, confidence=0.5)
        bad = Company(name="单休公司", level=4, confidence=0.8)
        s.add_all([white, dual, bad])
        s.flush()
        s.add(Evidence(company_id=white.id, source_type="review", url="https://z/1",
                       keywords="双休", raw_score=1.5, weight=0.9,
                       collected_at=date.today(), reviewed=False))
        s.commit()


class TestExport:
    def test_public_only_whitelist(self, tmp_path, monkeypatch):
        from scripts import export_data

        engine = _temp_db_engine()
        _seed(engine)
        monkeypatch.setattr(export_data, "DATA", tmp_path)
        monkeypatch.setattr(export_data, "LOCAL", tmp_path / "local")
        with Session(engine) as session:
            wl, jobs = export_data.export_public(session)
        assert wl == 2  # 仅 L1/L2

        payload = json.loads((tmp_path / "companies.json").read_text())
        assert payload["count"] == 2
        levels_seen = {c["level"] for c in payload["companies"]}
        assert levels_seen == {1, 2}  # 绝不出现 L3~L6
        # 证据内嵌且只含链接+关键词
        assert payload["companies"][0]["evidences"][0]["url"].startswith("https://")

    def test_local_full_contains_all(self, tmp_path, monkeypatch):
        from scripts import export_data

        engine = _temp_db_engine()
        _seed(engine)
        monkeypatch.setattr(export_data, "DATA", tmp_path)
        monkeypatch.setattr(export_data, "LOCAL", tmp_path / "local")
        with Session(engine) as session:
            export_data.export_local_full(session)
        payload = json.loads((tmp_path / "local" / "companies_all.json").read_text())
        assert payload["count"] == 3
        assert {c["level"] for c in payload["companies"]} == {1, 2, 4}


class TestMigrate:
    def test_migrate_idempotent(self):
        from scripts import migrate

        engine = _temp_db_engine()
        _seed(engine)
        migrate.run(engine)
        with engine.connect() as conn:
            v1 = conn.execute(text("SELECT COUNT(*) FROM schema_version")).scalar()
        assert v1 == len(migrate.MIGRATIONS)
        migrate.run(engine)  # 二次运行应跳过
        with engine.connect() as conn:
            v2 = conn.execute(text("SELECT COUNT(*) FROM schema_version")).scalar()
        assert v2 == v1

    def test_migrate_backfills_weight_snapshot(self):
        from scripts import migrate

        engine = _temp_db_engine()
        _seed(engine)
        # 模拟旧数据：weight=1.0（历史 bug）
        with Session(engine) as s:
            for ev in s.query(Evidence):
                ev.weight = 1.0
            s.commit()
        migrate.run(engine)
        with Session(engine) as s:
            ev = s.query(Evidence).first()
            assert ev.weight == levels.weight_for(ev.source_type)  # review → 0.9