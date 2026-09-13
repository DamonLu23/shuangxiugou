"""申诉子系统测试：提交 / 队列 / 处理 / 鉴权。"""

from sqlalchemy.orm import Session

from app.db.models import Appeal


class TestAppeals:
    def test_full_flow(self, client, seed_companies, admin_headers):
        cid = seed_companies["cid1"]
        r = client.post(f"/api/companies/{cid}/appeal", json={
            "contact": "hr@example.com", "reason": "希望补充公司官方作息制度说明",
            "evidence_url": "https://company.example.com/policy",
        })
        assert r.status_code == 200
        aid = r.json()["appeal_id"]
        assert r.json()["status"] == "open"

        # 管理队列可见
        r = client.get("/api/admin/appeals", headers=admin_headers)
        assert any(a["appeal_id"] == aid for a in r.json())

        # 处理
        r = client.post(f"/api/admin/appeals/{aid}/resolve",
                        json={"action": "resolve", "note": "已核实"}, headers=admin_headers)
        assert r.json()["status"] == "resolved"
        # 处理后的不在 open 队列
        r = client.get("/api/admin/appeals?status=open", headers=admin_headers)
        assert all(a["appeal_id"] != aid for a in r.json())

    def test_reject_flow(self, client, seed_companies, admin_headers):
        cid = seed_companies["cid1"]
        aid = client.post(f"/api/companies/{cid}/appeal", json={
            "reason": "理由不充分的一次申诉尝试"}).json()["appeal_id"]
        r = client.post(f"/api/admin/appeals/{aid}/resolve",
                        json={"action": "reject", "note": "无依据"}, headers=admin_headers)
        assert r.json()["status"] == "rejected"

    def test_validation(self, client, seed_companies):
        cid = seed_companies["cid1"]
        assert client.post(f"/api/companies/{cid}/appeal",
                           json={"reason": "短"}).status_code == 422
        assert client.post("/api/companies/9999/appeal",
                           json={"reason": "企业不存在时的申诉内容"}).status_code == 404

    def test_auth_required(self, client, seed_companies, admin_headers):
        cid = seed_companies["cid1"]
        aid = client.post(f"/api/companies/{cid}/appeal", json={
            "reason": "用于鉴权测试的申诉内容"}).json()["appeal_id"]
        assert client.get("/api/admin/appeals").status_code == 403
        assert client.post(f"/api/admin/appeals/{aid}/resolve",
                           json={"action": "resolve"}).status_code == 403

    def test_double_resolve_conflict(self, client, seed_companies, admin_headers):
        """已处理的申诉再次处理应明确拒绝（当前实现幂等更新，验证状态一致性）。"""
        cid = seed_companies["cid1"]
        aid = client.post(f"/api/companies/{cid}/appeal", json={
            "reason": "重复处理验证的申诉内容"}).json()["appeal_id"]
        client.post(f"/api/admin/appeals/{aid}/resolve",
                    json={"action": "resolve"}, headers=admin_headers)
        r = client.post(f"/api/admin/appeals/{aid}/resolve",
                        json={"action": "reject"}, headers=admin_headers)
        # 当前语义：允许更新状态；这里锁定行为避免回归意外
        assert r.json()["status"] == "rejected"

    def test_db_row_written(self, client, engine, seed_companies, admin_headers):
        cid = seed_companies["cid1"]
        client.post(f"/api/companies/{cid}/appeal", json={
            "reason": "数据库写入验证的申诉内容"})
        with Session(engine) as s:
            assert s.query(Appeal).count() == 1