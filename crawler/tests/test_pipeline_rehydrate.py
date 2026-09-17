"""白名单状态回灌 + 全量证据聚合单测（CI 分片状态恢复）。"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import pipeline  # noqa: E402
from app.db.models import Base, Company, Evidence  # noqa: E402
from sources.base import RawEvidence  # noqa: E402

WHITELIST_PAYLOAD = {
    "generated_at": "2026-09-16T00:00:00Z",
    "strategy": "测试",
    "count": 1,
    "companies": [{
        "id": 1,
        "name": "满帮集团有限公司",
        "level": 2,
        "confidence": 1.0,
        "disputed": False,
        "updated_at": "2026-09-16",
        "evidence_count": 2,
        "evidences": [
            {"source_type": "job_post", "url": "https://example.com/1",
             "keywords": ["周末双休", "双休"], "raw_score": -3.0, "weight": 0.4,
             "collected_at": "2026-09-10"},
            {"source_type": "job_post", "url": "https://example.com/2",
             "keywords": ["双休"], "raw_score": -3.0, "weight": 0.4,
             "collected_at": "2026-09-10"},
        ],
    }],
}


@pytest.fixture()
def tmp_env(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    json_path = tmp_path / "companies.json"
    json_path.write_text(json.dumps(WHITELIST_PAYLOAD, ensure_ascii=False),
                         encoding="utf-8")
    monkeypatch.setattr(pipeline, "DB_PATH", db_path)
    monkeypatch.setattr(pipeline, "COMPANIES_JSON", json_path)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


class TestSplitWhitelist:
    def test_splits_base_and_rest(self):
        companies = [
            {"key": "满帮", "full_name": "满帮集团有限公司"},
            {"key": "中兴通讯", "full_name": "中兴通讯股份有限公司"},
        ]
        base, rest = pipeline.split_whitelist(companies, {"满帮集团有限公司"})
        assert [c["key"] for c in base] == ["满帮"]
        assert [c["key"] for c in rest] == ["中兴通讯"]

    def test_empty_whitelist(self):
        companies = [{"key": "x", "full_name": "X有限公司"}]
        base, rest = pipeline.split_whitelist(companies, set())
        assert base == [] and rest == companies


class TestRehydrateWhitelist:
    def test_inserts_company_and_evidence(self, tmp_env):
        added = pipeline.rehydrate_whitelist(tmp_env, WHITELIST_PAYLOAD)
        assert added == 2
        with Session(tmp_env) as db:
            c = db.scalar(select(Company).where(Company.name == "满帮集团有限公司"))
            assert (c.level, c.confidence) == (2, 1.0)
            evs = db.scalars(select(Evidence).where(Evidence.company_id == c.id)).all()
            assert len(evs) == 2
            assert evs[0].collected_at == date(2026, 9, 10)

    def test_idempotent(self, tmp_env):
        pipeline.rehydrate_whitelist(tmp_env, WHITELIST_PAYLOAD)
        assert pipeline.rehydrate_whitelist(tmp_env, WHITELIST_PAYLOAD) == 0
        with Session(tmp_env) as db:
            assert len(db.scalars(select(Evidence)).all()) == 2

    def test_does_not_overwrite_local_levels(self, tmp_env):
        with Session(tmp_env) as db:
            db.add(Company(name="满帮集团有限公司", level=1, confidence=0.9))
            db.commit()
        pipeline.rehydrate_whitelist(tmp_env, WHITELIST_PAYLOAD)
        with Session(tmp_env) as db:
            c = db.scalar(select(Company).where(Company.name == "满帮集团有限公司"))
            assert (c.level, c.confidence) == (1, 0.9)  # 本地评级不被公开制品覆盖

    def test_empty_payload(self, tmp_env):
        assert pipeline.rehydrate_whitelist(tmp_env, {}) == 0


class TestWriteToDbAggregatesHistory:
    def test_incremental_evidence_included_in_aggregate(self, tmp_env):
        """回灌 2 条负分历史 + 本轮 1 条正分 → 按 3 条聚合（L4），而非只看本轮（L1）。"""
        pipeline.rehydrate_whitelist(tmp_env, WHITELIST_PAYLOAD)
        companies = [{"key": "满帮", "full_name": "满帮集团有限公司"}]
        new_ev = RawEvidence(
            company_key="满帮", company_raw="满帮集团有限公司",
            source_type="job_post", url="https://example.com/3",
            keywords=["周末双休"], raw_score=1.8,
        )
        pipeline.write_to_db(tmp_env, companies, [new_ev])
        with Session(tmp_env) as db:
            c = db.scalar(select(Company).where(Company.name == "满帮集团有限公司"))
            assert c.level == 4          # (-3-3+1.8)/3 = -1.4
            assert c.confidence > 0
