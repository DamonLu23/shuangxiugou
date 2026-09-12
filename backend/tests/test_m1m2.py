"""M1/M2 测试：求职白名单 / 岗位上报审核 / 企业申诉 / 好物目录。

使用独立临时库 + dependency_overrides；Job/Appeal/Goods 全链路。
"""

import csv
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Company, Evidence, Job, UgcReport
from app.db.session import get_db
from app.main import app

ADMIN = {"X-Admin-Token": "changeme-admin-token"}


@pytest.fixture()
def env():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        c1 = Company(name="双休科技股份有限公司", level=1, confidence=0.8)
        c2 = Company(name="单休制造股份有限公司", level=4, confidence=0.9)
        c3 = Company(name="待验证商贸股份有限公司", level=6, confidence=0.0)
        s.add_all([c1, c2, c3])
        s.flush()
        s.add_all([
            Job(title="后端工程师（周末双休）", company_id=c1.id, company_name=c1.name,
                city="杭州", tags="双休,五险一金", salary="15-25K", url="https://zp/j1",
                source="zhaopin", collected_at=date.today(), active=True),
            Job(title="工厂普工", company_id=c2.id, company_name=c2.name,
                city="东莞", tags="做六休一", url="https://zp/j2",
                source="zhaopin", collected_at=date.today(), active=True),
            Job(title="销售顾问", company_id=c3.id, company_name=c3.name,
                city="上海", url="https://zp/j3",
                source="zhaopin", collected_at=date.today(), active=True),
        ])
        s.commit()
        env = {"engine": e, "cid1": c1.id, "cid2": c2.id}
    yield env
    e.dispose()


@pytest.fixture()
def client(env):
    def override_get_db():
        s = Session(env["engine"])
        try:
            yield s
        finally:
            s.close()

    from app.routers import deps, jobs as jobs_mod
    deps._report_times.clear()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


class TestJobsSearch:
    def test_whitelist_only(self, client):
        """只有白名单企业的岗位可见；单休/待验证企业岗位不展示。"""
        r = client.get("/api/jobs/search", params={"q": "工程师"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["jobs"][0]["company_name"] == "双休科技股份有限公司"
        assert data["jobs"][0]["company_level"] == 1

    def test_non_whitelist_jobs_hidden_even_on_keyword_match(self, client):
        r = client.get("/api/jobs/search", params={"q": "普工"})
        assert r.json()["total"] == 0

    def test_city_filter(self, client):
        r = client.get("/api/jobs/search", params={"q": "工程师", "city": "上海"})
        assert r.json()["total"] == 0
        r2 = client.get("/api/jobs/search", params={"q": "工程师", "city": "杭州"})
        assert r2.json()["total"] == 1


class TestJobsReport:
    def test_report_ugc_whitelist_approve(self, client, env):
        """用户上报岗位 → 审核通过（企业白名单）→ 可见。"""
        r = client.post("/api/jobs/report", json={
            "title": "产品经理（双休）", "company_name": "双休科技股份有限公司",
            "city": "北京", "salary": "20-30K",
        })
        assert r.status_code == 200
        jid = r.json()["job_id"]

        # 未审核时仍不可见
        assert client.get("/api/jobs/search", params={"q": "产品经理"}).json()["total"] == 0
        assert client.get("/api/admin/jobs", headers=ADMIN).status_code == 200

        r = client.post(f"/api/admin/jobs/{jid}/review",
                        json={"action": "approve"}, headers=ADMIN)
        assert r.json()["status"] == "approved"
        assert client.get("/api/jobs/search", params={"q": "产品经理"}).json()["total"] == 1

    def test_report_ugc_non_whitelist_held(self, client, env):
        """非白名单企业的岗位审核通过也会被挂起，永不展示。"""
        r = client.post("/api/jobs/report", json={
            "title": "质检员", "company_name": "单休制造股份有限公司"})
        jid = r.json()["job_id"]
        r = client.post(f"/api/admin/jobs/{jid}/review",
                        json={"action": "approve"}, headers=ADMIN)
        assert r.json()["status"] == "held"
        assert client.get("/api/jobs/search", params={"q": "质检员"}).json()["total"] == 0

    def test_report_reject(self, client, env):
        r = client.post("/api/jobs/report", json={
            "title": "虚假岗位", "company_name": "双休科技股份有限公司"})
        jid = r.json()["job_id"]
        assert client.post(f"/api/admin/jobs/{jid}/review",
                           json={"action": "reject"}, headers=ADMIN).json()["status"] == "rejected"
        assert client.get("/api/jobs/search", params={"q": "虚假岗位"}).json()["total"] == 0

    def test_report_validation_and_auth(self, client):
        assert client.post("/api/jobs/report", json={"title": "短"}).status_code == 422
        assert client.get("/api/admin/jobs").status_code == 403


class TestAppeals:
    def test_appeal_flow(self, client, env):
        r = client.post(f"/api/companies/{env['cid1']}/appeal", json={
            "contact": "hr@example.com", "reason": "希望补充公司官方作息制度说明",
            "evidence_url": "https://company.example.com/policy",
        })
        assert r.status_code == 200
        aid = r.json()["appeal_id"]
        assert r.json()["status"] == "open"

        assert client.get("/api/admin/appeals", headers=ADMIN).status_code == 200
        r = client.post(f"/api/admin/appeals/{aid}/resolve",
                        json={"action": "resolve", "note": "已核实并补充证据"}, headers=ADMIN)
        assert r.json()["status"] == "resolved"
        # 无 token 被拒
        assert client.post(f"/api/admin/appeals/{aid}/resolve",
                           json={"action": "resolve"}).status_code == 403

    def test_appeal_reason_required(self, client, env):
        r = client.post(f"/api/companies/{env['cid1']}/appeal", json={"reason": "短"})
        assert r.status_code == 422


class TestGoods:
    def test_goods_whitelist_only(self, client, tmp_path):
        """好物目录：非白名单企业商品被过滤。"""
        from app.routers import goods as goods_mod

        csv_path = tmp_path / "goods.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["company_name", "category", "product", "official_link", "note"])
            w.writerow(["双休科技股份有限公司", "互联网", "双休云服务", "https://sxg.io", ""])
            w.writerow(["单休制造股份有限公司", "制造", "单休机床", "https://dx.io", ""])
        goods_mod.GOODS_CSV = csv_path
        try:
            r = client.get("/api/goods/search", params={"q": "云"})
            items = r.json()["items"]
            assert len(items) == 1
            assert items[0]["company_name"] == "双休科技股份有限公司"
            assert items[0]["company_level"] == 1

            r2 = client.get("/api/goods/search", params={"q": "机床"})
            assert r2.json()["total"] == 0
        finally:
            goods_mod.GOODS_CSV = goods_mod.GOODS_CSV  # 恢复由后续 fixture 内替换
        object.__setattr__(goods_mod, "GOODS_CSV",
                           Path(__file__).resolve().parents[2] / "data" / "goods.csv")