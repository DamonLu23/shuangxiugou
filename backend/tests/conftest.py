"""共享测试夹具：临时库 + FastAPI 测试客户端 + 样例企业。

每个测试文件独立可跑（pytest tests/test_xxx.py），不依赖开发数据库。
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Company
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def engine():
    """独立临时 SQLite 库。"""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture()
def client(engine):
    """替换 get_db 的测试客户端（并重置 UGC 限流状态）。"""
    def override_get_db():
        s = Session(engine)
        try:
            yield s
        finally:
            s.close()

    from app.routers import deps
    deps._report_times.clear()
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def admin_headers():
    return {"X-Admin-Token": "changeme-admin-token"}


@pytest.fixture()
def seed_companies(engine):
    """三家样例企业：白名单双休 / 单休 / 待验证。"""
    with Session(engine) as s:
        c1 = Company(name="双休科技股份有限公司", level=1, confidence=0.8)
        c2 = Company(name="单休制造股份有限公司", level=4, confidence=0.9)
        c3 = Company(name="待验证商贸股份有限公司", level=6, confidence=0.0)
        s.add_all([c1, c2, c3])
        s.commit()
        return {"cid1": c1.id, "cid2": c2.id, "cid3": c3.id}