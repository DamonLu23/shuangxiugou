"""pipeline 新鲜度分片（--stale-days）单测。"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import pipeline  # noqa: E402
from app.db.models import Base, Company, Evidence  # noqa: E402


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(pipeline, "DB_PATH", db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        fresh = Company(name="新鲜公司", level=6, confidence=0)
        old = Company(name="过期公司", level=6, confidence=0)
        s.add_all([fresh, old])
        s.flush()
        s.add(Evidence(company_id=fresh.id, source_type="review", url="u1",
                       collected_at=date.today()))
        s.add(Evidence(company_id=old.id, source_type="review", url="u2",
                       collected_at=date.today() - timedelta(days=40)))
        s.commit()
    return engine


COMPANIES = [
    {"key": "新鲜", "full_name": "新鲜公司"},
    {"key": "过期", "full_name": "过期公司"},
    {"key": "缺证据", "full_name": "缺证据公司"},
]


def test_stale_filter_selects_expired_and_missing(tmp_db):
    got = {c["full_name"] for c in pipeline.filter_stale(COMPANIES, 28)}
    assert got == {"过期公司", "缺证据公司"}


def test_stale_filter_boundary(tmp_db):
    got = {c["full_name"] for c in pipeline.filter_stale(COMPANIES, 90)}
    assert got == {"缺证据公司"}


class TestChunkCompanies:
    def test_chunks_are_disjoint_and_cover_all(self):
        companies = [{"key": f"公司{i}", "full_name": f"公司{i}有限公司"} for i in range(200)]
        parts = [pipeline.chunk_companies(companies, f"{k}/4") for k in range(1, 5)]
        keys = [c["key"] for part in parts for c in part]
        assert sorted(keys) == sorted(c["key"] for c in companies)  # 不重不漏

    def test_chunk_is_deterministic(self):
        companies = [{"key": f"公司{i}", "full_name": "x"} for i in range(50)]
        a = {c["key"] for c in pipeline.chunk_companies(companies, "1/3")}
        b = {c["key"] for c in pipeline.chunk_companies(companies, "1/3")}
        assert a == b and a  # 同一分片可复现

    def test_invalid_spec_rejected(self):
        with pytest.raises(ValueError):
            pipeline.chunk_companies([], "5/4")
