"""求职子系统测试：白名单岗位搜索 / 分页 / UGC 岗位上报与审核。"""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.models import Job


@pytest.fixture()
def seeded_jobs(engine, seed_companies):
    """三种企业的岗位：白名单（可见）/ 单休 / 待验证（均不可见）。"""
    with Session(engine) as s:
        s.add_all([
            Job(title="后端工程师（周末双休）", company_id=seed_companies["cid1"],
                company_name="双休科技股份有限公司", city="杭州",
                tags="双休,五险一金", salary="15-25K", url="https://zp/j1",
                source="zhaopin", collected_at=date.today(), active=True),
            Job(title="工厂普工", company_id=seed_companies["cid2"],
                company_name="单休制造股份有限公司", city="东莞",
                tags="做六休一", url="https://zp/j2",
                source="zhaopin", collected_at=date.today(), active=True),
            Job(title="销售顾问", company_id=seed_companies["cid3"],
                company_name="待验证商贸股份有限公司", city="上海",
                url="https://zp/j3",
                source="zhaopin", collected_at=date.today(), active=True),
        ])
        s.commit()
    return seed_companies


class TestJobsSearch:
    def test_whitelist_only(self, client, seeded_jobs):
        r = client.get("/api/jobs/search", params={"q": "工程师"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["jobs"][0]["company_name"] == "双休科技股份有限公司"
        assert data["jobs"][0]["company_level"] == 1
        assert data["jobs"][0]["company_level_name"] == "严格双休"

    def test_non_whitelist_hidden(self, client, seeded_jobs):
        for q in ("普工", "销售"):
            assert client.get("/api/jobs/search", params={"q": q}).json()["total"] == 0

    def test_city_filter(self, client, seeded_jobs):
        assert client.get("/api/jobs/search",
                          params={"q": "工程师", "city": "上海"}).json()["total"] == 0
        assert client.get("/api/jobs/search",
                          params={"q": "工程师", "city": "杭州"}).json()["total"] == 1

    def test_inactive_jobs_hidden(self, client, engine, seeded_jobs):
        with Session(engine) as s:
            s.query(Job).update({Job.active: False})
            s.commit()
        assert client.get("/api/jobs/search", params={"q": "工程师"}).json()["total"] == 0

    def test_pagination_shape(self, client, seeded_jobs):
        r = client.get("/api/jobs/search", params={"q": "工程师", "page": 2, "page_size": 20})
        data = r.json()
        assert data["page"] == 2
        assert data["jobs"] == []  # 仅 1 条，第 2 页为空


class TestJobsReport:
    def test_report_approve_whitelist(self, client, seeded_jobs, admin_headers):
        r = client.post("/api/jobs/report", json={
            "title": "产品经理（双休）", "company_name": "双休科技股份有限公司",
            "city": "北京", "salary": "20-30K",
        })
        assert r.status_code == 200
        jid = r.json()["job_id"]
        assert client.get("/api/jobs/search", params={"q": "产品经理"}).json()["total"] == 0

        r = client.post(f"/api/admin/jobs/{jid}/review",
                        json={"action": "approve"}, headers=admin_headers)
        assert r.json()["status"] == "approved"
        assert client.get("/api/jobs/search", params={"q": "产品经理"}).json()["total"] == 1

    def test_report_held_for_non_whitelist(self, client, seeded_jobs, admin_headers):
        r = client.post("/api/jobs/report", json={
            "title": "质检员", "company_name": "单休制造股份有限公司"})
        jid = r.json()["job_id"]
        r = client.post(f"/api/admin/jobs/{jid}/review",
                        json={"action": "approve"}, headers=admin_headers)
        assert r.json()["status"] == "held"
        assert client.get("/api/jobs/search", params={"q": "质检员"}).json()["total"] == 0

    def test_report_reject(self, client, seeded_jobs, admin_headers):
        r = client.post("/api/jobs/report", json={
            "title": "虚假岗位", "company_name": "双休科技股份有限公司"})
        jid = r.json()["job_id"]
        assert client.post(f"/api/admin/jobs/{jid}/review",
                           json={"action": "reject"}, headers=admin_headers
                           ).json()["status"] == "rejected"
        assert client.get("/api/jobs/search", params={"q": "虚假岗位"}).json()["total"] == 0

    def test_report_validation_and_auth(self, client, seeded_jobs):
        assert client.post("/api/jobs/report", json={"title": "短"}).status_code == 422
        assert client.get("/api/admin/jobs").status_code == 403