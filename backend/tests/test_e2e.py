"""整体测试（端到端）：跨子系统全链路场景。

场景 A：用户全旅程（证据 → 审核 → 进白名单 → 岗位/好物可见 → 申诉/纠错闭环）
场景 B：白名单防线（非白名单企业在所有公开接口不可见）
"""

import csv
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import Company, Job
from app.routers import goods as goods_mod


class TestUserJourney:
    """一家 L6 待验证企业如何走完「证据 → 白名单 → 岗位/好物 → 申诉」全流程。"""

    def test_full_journey(self, client, engine, admin_headers, seed_companies,
                          tmp_path, monkeypatch):
        cid = seed_companies["cid3"]  # 待验证商贸股份有限公司（L6）
        name = "待验证商贸股份有限公司"

        # 0) 起点：不在白名单（列表/详情均不可见）
        assert name not in [x["name"] for x in client.get("/api/companies").json()]
        assert client.get(f"/api/companies/{cid}").status_code == 404

        # 1) 用户提交合同证据（UGC）
        r = client.post(f"/api/companies/{cid}/report", json={
            "source_type": "ugc_contract",
            "description": "劳动合同明确约定做五休二，周末双休，法定节假日休息",
        })
        assert r.status_code == 200
        rid = r.json()["report_id"]

        # 2) 管理员审核通过 → 等级重算入白名单
        r = client.post(f"/api/admin/reports/{rid}/review",
                        json={"action": "approve"}, headers=admin_headers)
        assert r.json()["company_level"] == 1

        # 3) 企业进入公开白名单（列表 + 详情 + 证据可溯源）
        assert name in [x["name"] for x in client.get("/api/companies").json()]
        detail = client.get(f"/api/companies/{cid}").json()
        assert detail["level"] == 1
        assert detail["evidence_count"] == 1
        assert detail["evidences"][0]["source_type"] == "ugc_contract"

        # 4) 用户报岗位 → 审核通过 → 求职搜索可见
        r = client.post("/api/jobs/report", json={
            "title": "会计（周末双休）", "company_name": name, "city": "上海"})
        jid = r.json()["job_id"]
        assert client.get("/api/jobs/search", params={"q": "会计"}).json()["total"] == 0
        client.post(f"/api/admin/jobs/{jid}/review",
                    json={"action": "approve"}, headers=admin_headers)
        jobs = client.get("/api/jobs/search", params={"q": "会计"}).json()
        assert jobs["total"] == 1
        assert jobs["jobs"][0]["company_level"] == 1

        # 5) 好物目录新增该企业商品（社区 PR 场景）→ 搜索可见
        csv_path = tmp_path / "goods.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["company_name", "category", "product", "official_link", "note"])
            w.writerow([name, "商贸", "双休优选礼盒", "https://example.com/gift", ""])
        monkeypatch.setattr(goods_mod, "GOODS_CSV", csv_path)
        goods = client.get("/api/goods/search", params={"q": "礼盒"}).json()
        assert goods["total"] == 1
        assert goods["items"][0]["company_level"] == 1

        # 6) 企业申诉 → 管理员处理（闭环）
        aid = client.post(f"/api/companies/{cid}/appeal", json={
            "reason": "希望补充官方作息制度链接以提升置信度",
            "evidence_url": "https://example.com/policy",
        }).json()["appeal_id"]
        r = client.post(f"/api/admin/appeals/{aid}/resolve",
                        json={"action": "resolve", "note": "已核实"}, headers=admin_headers)
        assert r.json()["status"] == "resolved"

        # 7) 数据纠错（三表单之三）→ 入队
        r = client.post("/api/feedback/correction", json={
            "target": "岗位数据", "subject": name, "detail": "岗位链接已失效，请核验",
        })
        assert r.status_code == 200


class TestWhitelistDefense:
    """白名单防线：非白名单企业在 4 个子系统的所有公开入口均不可见。"""

    def test_defense_across_subsystems(self, client, engine, seed_companies,
                                       admin_headers, tmp_path, monkeypatch):
        bad_id = seed_companies["cid2"]      # 单休制造股份有限公司 L4
        bad_name = "单休制造股份有限公司"

        # 预置：L4 企业的岗位与好物
        with Session(engine) as s:
            s.add(Job(title="车间主管", company_id=bad_id, company_name=bad_name,
                      city="东莞", url="https://zp/bad", source="zhaopin",
                      collected_at=date.today(), active=True))
            s.commit()
        csv_path = tmp_path / "goods.csv"
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["company_name", "category", "product", "official_link", "note"])
            w.writerow([bad_name, "制造", "机床设备", "https://dx.io", ""])
        monkeypatch.setattr(goods_mod, "GOODS_CSV", csv_path)

        # ① 企业榜：不出现
        assert bad_name not in [x["name"] for x in client.get("/api/companies").json()]
        # ② 企业档案：404
        assert client.get(f"/api/companies/{bad_id}").status_code == 404
        # ③ 求职搜索：岗位不可见（即使 active）
        assert client.get("/api/jobs/search", params={"q": "车间主管"}).json()["total"] == 0
        # ④ 好物目录：商品被过滤
        assert client.get("/api/goods/search", params={"q": "机床"}).json()["total"] == 0

        # ⑤ UGC 岗位上报该企业 → 审核通过也强制挂起
        r = client.post("/api/jobs/report", json={
            "title": "质检员", "company_name": bad_name})
        jid = r.json()["job_id"]
        r = client.post(f"/api/admin/jobs/{jid}/review",
                        json={"action": "approve"}, headers=admin_headers)
        assert r.json()["status"] == "held"
        assert client.get("/api/jobs/search", params={"q": "质检员"}).json()["total"] == 0

    def test_level_downgrade_removes_from_whitelist(self, client, engine,
                                                    seed_companies):
        """企业降级后（例如新证据翻盘）所有公开入口立即不可见。"""
        cid = seed_companies["cid1"]  # 起始 L1
        assert client.get(f"/api/companies/{cid}").status_code == 200
        with Session(engine) as s:
            c = s.get(Company, cid)
            c.level = 4  # 模拟重算降级
            s.commit()
        assert client.get(f"/api/companies/{cid}").status_code == 404
        assert "双休科技股份有限公司" not in [
            x["name"] for x in client.get("/api/companies").json()]