"""UGC 上报 → 审核队列 → 通过转证据 → 企业等级重算 全链路测试。

使用独立临时 SQLite 库 + FastAPI dependency_overrides（不污染开发数据）。
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Company, Evidence, UgcReport
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def client():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Company(name="测试科技股份有限公司", level=6, confidence=0.0))
        s.commit()

    def override_get_db():
        s = Session(e)
        try:
            yield s
        finally:
            s.close()

    from app.routers import deps
    deps._report_times.clear()  # 重置限流状态
    app.dependency_overrides[get_db] = override_get_db
    yield {"tc": TestClient(app), "engine": e}
    app.dependency_overrides.pop(get_db, None)


ADMIN = {"X-Admin-Token": "changeme-admin-token"}


def test_flow(client):
    tc = client["tc"]
    engine = client["engine"]
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        cid = s.query(Company).first().id

    # 1. 上报成功，进入 pending
    r = tc.post(f"/api/companies/{cid}/report", json={
        "source_type": "ugc_contract",
        "description": "劳动合同明确约定做五休二，周末双休，法定节假日休息",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    rid = r.json()["report_id"]

    with Session(engine) as s:
        rp = s.get(UgcReport, rid)
        assert rp.status == "pending"

    # 2. 未审核前企业仍是 L6
    with Session(engine) as s:
        assert s.get(Company, cid).level == 6

    # 3. 无 token 审核被拒
    assert tc.post(f"/api/admin/reports/{rid}/review",
                   json={"action": "approve"}).status_code == 403

    # 4. 审核通过 → 转证据（权重快照 1.0）+ 重算为 L1
    r = tc.post(f"/api/admin/reports/{rid}/review",
                json={"action": "approve"}, headers=ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert "做五休二" in data["keywords"] and "双休" in data["keywords"]
    assert data["company_level"] == 1
    assert data["company_confidence"] > 0

    with Session(engine) as s:
        ev = s.query(Evidence).filter(Evidence.source_type == "ugc_contract").one()
        assert "做五休二" in ev.keywords and "双休" in ev.keywords
        assert ev.weight == 1.0  # 权重快照入库
        company = s.get(Company, cid)
        assert company.level == 1
        assert company.confidence > 0.3  # 单条合同证据权重 1.0/3 = 0.33

    # 5. 重复审核被拒（409）
    assert tc.post(f"/api/admin/reports/{rid}/review",
                   json={"action": "approve"}, headers=ADMIN).status_code == 409

    # 6. 第二条负面上报：与合同证据折中，不应再是 L1
    r = tc.post(f"/api/companies/{cid}/report", json={
        "source_type": "ugc_other",
        "description": "实际上班做六休一，经常996，大小周轮换",
    })
    rid2 = r.json()["report_id"]
    r = tc.post(f"/api/admin/reports/{rid2}/review", json={"action": "approve"},
                headers=ADMIN)
    assert r.status_code == 200
    # 合同证据(权重1.0) + 口头负面(0.5) 折中 → 不应再是 L1
    assert r.json()["company_level"] != 1

    # 7. 审核队列列表可见
    r = tc.get("/api/admin/reports?status=approved", headers=ADMIN)
    assert r.status_code == 200
    assert len(r.json()) == 2

    # 8. 驳回路径
    r = tc.post(f"/api/companies/{cid}/report", json={
        "source_type": "ugc_offer",
        "description": "offer 写周末双休，试用期大小周",
    })
    rid3 = r.json()["report_id"]
    r = tc.post(f"/api/admin/reports/{rid3}/review",
                json={"action": "reject", "note": "截图模糊无法核实"}, headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_validation(client):
    tc = client["tc"]
    # 非法来源与过短描述
    assert tc.post("/api/companies/999/report", json={
        "source_type": "evil", "description": "x"
    }).status_code == 422
    # 不存在企业
    assert tc.post("/api/companies/9999/report", json={
        "source_type": "ugc_other", "description": "我是员工希望补充真实情况"
    }).status_code == 404
