"""Phase1 测试：反馈 → GitHub Issue 无感通道（三表单 × 三态）。

三态：无 token 降级 / token 正常创建 / GitHub 异常降级。
用户数据无论哪种状态都必须入库（不丢数据）。
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Appeal, Base, Company, Job, UgcReport
from app.db.session import get_db
from app.main import app
from app.services import github_feedback


@pytest.fixture()
def env(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        c = Company(name="双休科技股份有限公司", level=1, confidence=0.8)
        s.add(c)
        s.commit()
        env = {"engine": e, "cid": c.id}

    def override_get_db():
        s = Session(e)
        try:
            yield s
        finally:
            s.close()

    from app.routers import deps
    deps._report_times.clear()
    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr(settings, "github_token", "")  # 默认：无 token
    yield env
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client(env):
    return TestClient(app)


class TestNoTokenDegrade:
    def test_job_report_degrades(self, client, env):
        r = client.post("/api/jobs/report", json={
            "title": "运营专员（双休）", "company_name": "双休科技股份有限公司", "city": "北京",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["issue_url"] is None
        assert "审核通过" in data["message"]
        with Session(env["engine"]) as s:
            assert s.query(Job).filter(Job.source == "ugc").count() == 1  # 数据不丢

    def test_appeal_degrades(self, client, env):
        r = client.post(f"/api/companies/{env['cid']}/appeal", json={
            "reason": "希望补充官方作息制度说明", "contact": "hr@x.com",
        })
        assert r.json()["issue_url"] is None
        with Session(env["engine"]) as s:
            assert s.query(Appeal).count() == 1

    def test_correction_degrades(self, client, env):
        r = client.post("/api/feedback/correction", json={
            "target": "企业档案", "subject": "双休科技股份有限公司",
            "detail": "官网链接已变更为新地址",
        })
        assert r.status_code == 200
        assert r.json()["issue_url"] is None
        with Session(env["engine"]) as s:
            assert s.query(UgcReport).filter(UgcReport.source_type == "correction").count() == 1


class TestTokenIssue:
    def test_job_report_creates_issue(self, client, env, monkeypatch):
        monkeypatch.setattr(settings, "github_token", "test-token")
        calls = {}

        async def fake_post(kind, payload):
            calls["kind"], calls["payload"] = kind, payload
            return "https://github.com/DamonLu23/shuangxiugou/issues/1"

        monkeypatch.setattr(github_feedback, "_post_issue", fake_post)
        r = client.post("/api/jobs/report", json={
            "title": "后端工程师", "company_name": "双休科技股份有限公司",
            "city": "杭州", "salary": "15-25K", "url": "https://zp/j1",
        })
        assert r.json()["issue_url"] == "https://github.com/DamonLu23/shuangxiugou/issues/1"
        assert calls["kind"] == "job-report"
        assert calls["payload"]["company_name"] == "双休科技股份有限公司"

    def test_appeal_creates_issue_with_company_name(self, client, env, monkeypatch):
        monkeypatch.setattr(settings, "github_token", "test-token")

        async def fake_post(kind, payload):
            return f"https://github.com/issues/2?kind={kind}"

        monkeypatch.setattr(github_feedback, "_post_issue", fake_post)
        r = client.post(f"/api/companies/{env['cid']}/appeal", json={
            "reason": "请更正档案信息", "contact": "hr@x.com",
        })
        assert "kind=appeal" in r.json()["issue_url"]

    def test_correction_creates_issue(self, client, monkeypatch):
        monkeypatch.setattr(settings, "github_token", "test-token")

        async def fake_post(kind, payload):
            return "https://github.com/issues/3"

        monkeypatch.setattr(github_feedback, "_post_issue", fake_post)
        r = client.post("/api/feedback/correction", json={
            "target": "岗位数据", "subject": "某企业岗位", "detail": "岗位已下架但仍在展示",
        })
        assert r.json()["issue_url"] == "https://github.com/issues/3"


class TestGithubFailureDegrade:
    def test_github_error_degrades_and_keeps_data(self, client, env, monkeypatch):
        monkeypatch.setattr(settings, "github_token", "test-token")

        async def broken_post(kind, payload):
            raise RuntimeError("GitHub 502")

        monkeypatch.setattr(github_feedback, "_post_issue", broken_post)
        r = client.post("/api/jobs/report", json={
            "title": "测试岗位", "company_name": "双休科技股份有限公司",
        })
        assert r.status_code == 200
        assert r.json()["issue_url"] is None  # 降级
        with Session(env["engine"]) as s:
            assert s.query(Job).filter(Job.source == "ugc").count() == 1  # 数据照常入库


class TestValidation:
    def test_correction_validation(self, client):
        assert client.post("/api/feedback/correction", json={
            "subject": "x", "detail": "短"
        }).status_code == 422

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValueError):
            import asyncio
            asyncio.run(github_feedback.create_issue("evil", {}))