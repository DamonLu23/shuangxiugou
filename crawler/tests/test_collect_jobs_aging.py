"""岗位入库老化行为单测（避免运行失败误删岗位）。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import collect_jobs  # noqa: E402
from app.db.models import Base, Company, Job  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(collect_jobs, "engine", engine)
    with Session(engine) as db:
        company = Company(name="测试有限公司", level=1, confidence=1.0)
        db.add(company)
        db.flush()
        db.add(Job(title="旧岗位A", company_id=company.id, company_name=company.name,
                   url="https://example.com/old-a", source="zhaopin", active=True))
        db.add(Job(title="旧岗位B", company_id=company.id, company_name=company.name,
                   url="https://example.com/old-b", source="zhaopin", active=True))
        db.add(Job(title="官网旧岗", company_id=company.id, company_name=company.name,
                   url="https://example.com/old-official", source="official", active=True))
        db.commit()
        company_id = company.id
    with Session(engine) as db:
        company = db.get(Company, company_id)
    return engine, company


def _active_urls(engine):
    with Session(engine) as db:
        return {j.url for j in db.scalars(select(Job).where(Job.active.is_(True)))}


class TestSaveJobsAging:
    def test_ages_uncollected_when_source_succeeded(self, env):
        engine, company = env
        jobs = [{"title": "新岗位", "url": "https://example.com/new", "source": "zhaopin"}]
        collect_jobs._save_jobs(company, "测试", jobs, set(), age_sources={"zhaopin"})
        active = _active_urls(engine)
        # 两条旧 zhaopin 岗位被老化；official 不在本轮老化来源，保留
        assert active == {"https://example.com/new", "https://example.com/old-official"}

    def test_does_not_age_when_source_failed(self, env):
        engine, company = env
        collect_jobs._save_jobs(company, "测试", [], set(), age_sources=set())
        active = _active_urls(engine)
        assert len(active) == 3  # 来源失败：岗位全部保留

    def test_ages_only_target_source(self, env):
        engine, company = env
        collect_jobs._save_jobs(company, "测试", [], set(), age_sources={"official"})
        active = _active_urls(engine)
        assert "https://example.com/old-official" not in active
        assert {"https://example.com/old-a", "https://example.com/old-b"} <= active

    def test_recollected_url_reactivated(self, env):
        engine, company = env
        already = {"https://example.com/old-a", "https://example.com/old-b",
                   "https://example.com/old-official"}  # 生产：预载 DB 全部 URL
        jobs = [{"title": "旧岗位A", "url": "https://example.com/old-a",
                 "source": "zhaopin"}]
        added = collect_jobs._save_jobs(company, "测试", jobs, already,
                                        age_sources={"zhaopin"})
        assert added == 0  # 已存在不重复插入
        active = _active_urls(engine)
        assert "https://example.com/old-a" in active
        assert "https://example.com/old-b" not in active  # 未复现的仍老化

    def test_new_job_inserted_active(self, env):
        engine, company = env
        jobs = [{"title": "新岗位", "url": "https://example.com/new",
                 "source": "zhaopin", "city": "杭州", "welfare": ["双休"]}]
        added = collect_jobs._save_jobs(company, "测试", jobs, set(), age_sources={"zhaopin"})
        assert added == 1
        with Session(engine) as db:
            job = db.scalar(select(Job).where(Job.url == "https://example.com/new"))
            assert job.active is True and job.city == "杭州" and job.tags == "双休"
