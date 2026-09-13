"""共享依赖测试：管理鉴权 / UGC 限流。"""

from app.routers import deps


class TestAdminAuth:
    def test_all_admin_endpoints_require_token(self, client, seed_companies):
        """所有管理端点未带 token 一律 403（覆盖式防线）。"""
        checks = [
            ("get", "/api/admin/jobs", None),
            ("get", "/api/admin/appeals", None),
            ("get", "/api/admin/reports", None),
        ]
        for method, path, _ in checks:
            assert getattr(client, method)(path).status_code == 403, path

    def test_wrong_token_403(self, client, seed_companies):
        r = client.get("/api/admin/jobs", headers={"X-Admin-Token": "wrong"})
        assert r.status_code == 403


class TestRateLimit:
    def test_ugc_rate_limit(self, client, seed_companies):
        cid = seed_companies["cid1"]
        for i in range(deps.RATE_LIMIT):
            assert client.post(f"/api/companies/{cid}/report", json={
                "source_type": "ugc_other",
                "description": f"第{i}条正常描述，内容超过五个字",
            }).status_code == 200
        # 超限
        assert client.post(f"/api/companies/{cid}/report", json={
            "source_type": "ugc_other", "description": "超出限额的第六条上报内容",
        }).status_code == 429

    def test_correction_shares_rate_limit(self, client, seed_companies):
        for i in range(deps.RATE_LIMIT):
            client.post("/api/feedback/correction", json={
                "subject": "顺丰速运有限公司", "detail": f"第{i}条纠错描述内容",
            })
        r = client.post("/api/feedback/correction", json={
            "subject": "顺丰速运有限公司", "detail": "超限的纠错提交内容",
        })
        assert r.status_code == 429

    def test_different_ips_isolated(self, client, seed_companies):
        """限流按 IP 隔离（TestClient 固定 host，这里直接操作依赖函数验证滑窗语义）。"""
        deps._report_times.clear()
        deps.check_rate_limit("ip-a")
        deps.check_rate_limit("ip-b")
        assert len(deps._report_times["ip-a"]) == 1
        assert len(deps._report_times["ip-b"]) == 1