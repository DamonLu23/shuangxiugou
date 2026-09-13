"""企业档案子系统测试：白名单列表 / 筛选 / 详情 / 证据摘要。

白名单承诺：对外只返回 L1/L2 企业；L3~L6 详情一律 404。
"""

from datetime import date

from sqlalchemy.orm import Session

from app.db.models import Company, Evidence


def _add_evidence(engine, cid, score=1.5):
    with Session(engine) as s:
        s.add(Evidence(company_id=cid, source_type="review", url="https://zh/1",
                       keywords="双休,五险一金", raw_score=score, weight=0.9,
                       collected_at=date.today(), reviewed=False))
        s.commit()


def _add_company(engine, name, level):
    with Session(engine) as s:
        c = Company(name=name, level=level, confidence=0.4)
        s.add(c)
        s.commit()
        return c.id


class TestCompanyList:
    def test_only_whitelist_returned(self, client, seed_companies):
        rows = client.get("/api/companies").json()
        # 样例库中只有 1 家 L1 是白名单（L4/L6 不出现）
        assert [r["name"] for r in rows] == ["双休科技股份有限公司"]
        assert rows[0]["level"] == 1
        assert rows[0]["level_name"] == "严格双休"

    def test_level_filter(self, client, seed_companies, engine):
        _add_company(engine, "双休乙公司", 2)
        r = client.get("/api/companies", params={"level": 1})
        assert [x["name"] for x in r.json()] == ["双休科技股份有限公司"]
        r2 = client.get("/api/companies", params={"level": 2})
        assert [x["name"] for x in r2.json()] == ["双休乙公司"]

    def test_limit(self, client, seed_companies, engine):
        _add_company(engine, "双休乙公司", 2)
        assert len(client.get("/api/companies", params={"limit": 1}).json()) == 1

    def test_non_whitelist_never_listed(self, client, engine, seed_companies):
        """L3~L6 企业即使置信度更高也不出现在列表中。"""
        _add_company(engine, "高置信单休公司", 4)
        names = [r["name"] for r in client.get("/api/companies", params={"limit": 200}).json()]
        assert "高置信单休公司" not in names
        assert "单休制造股份有限公司" not in names
        assert "待验证商贸股份有限公司" not in names


class TestCompanyDetail:
    def test_detail_with_evidences(self, client, engine, seed_companies):
        cid = seed_companies["cid1"]
        _add_evidence(engine, cid)
        r = client.get(f"/api/companies/{cid}")
        d = r.json()
        assert d["id"] == cid
        assert d["level"] == 1
        assert d["level_name"] == "严格双休"
        assert d["evidence_count"] == 1
        ev = d["evidences"][0]
        assert {"source_type", "url", "keywords", "raw_score", "collected_at"} <= set(ev)
        assert ev["keywords"] == ["双休", "五险一金"]

    def test_non_whitelist_detail_404(self, client, seed_companies):
        """白名单防线：L4/L6 企业详情不可访问。"""
        assert client.get(f"/api/companies/{seed_companies['cid2']}").status_code == 404
        assert client.get(f"/api/companies/{seed_companies['cid3']}").status_code == 404

    def test_detail_404(self, client, seed_companies):
        assert client.get("/api/companies/9999").status_code == 404

    def test_confidence_rounded(self, client, seed_companies):
        r = client.get(f"/api/companies/{seed_companies['cid1']}")
        conf = r.json()["confidence"]
        assert isinstance(conf, float)
        assert round(conf, 3) == conf