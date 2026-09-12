"""M2 商品链路测试：品牌映射 / 联盟签名 / 搜索→打标→排序 / indexed_only。

使用独立临时库 + FastAPI dependency_overrides + mock 联盟（未配 AppKey 时自动 mock）。
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
from app.services import brand as brand_mod
from app.services.brand import import_seed, normalize_brand
from app.services.mall import MallClient, build_params


@pytest.fixture()
def engine():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        import_seed(s)
    yield e


@pytest.fixture()
def client(engine):
    def override_get_db():
        s = Session(engine)
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def _seed_engine() -> object:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        import_seed(s)
    return e


class TestBrandMapping:
    def test_normalize(self):
        assert normalize_brand(" op po ") == "OPPO"

    def test_longest_match_title(self):
        with Session(_seed_engine()) as s:
            lookup = brand_mod.build_lookup(s)
            assert brand_mod.extract_brand("华为官方旗舰店 智慧屏 新品", lookup) == "华为"
            assert brand_mod.extract_brand("OPPOReno11 5G手机 官方", lookup) == "OPPO"
            assert brand_mod.extract_brand("无品牌lv包 特价", lookup) is None

    def test_import_seed_idempotent(self):
        e = _seed_engine()
        with Session(e) as s:
            assert len(brand_mod.build_lookup(s)) >= 200
            import_seed(s)  # 二次导入应幂等
            assert len(brand_mod.build_lookup(s)) >= 200


class TestMallSign:
    def test_sign_stable_and_detects_tamper(self):
        p1 = build_params("taobao.tbk.dg.material.optional",
                          "test_key", "test_secret", {"q": "键盘", "page_no": 1})
        sign1 = p1.pop("sign")
        p2 = build_params("taobao.tbk.dg.material.optional",
                          "test_key", "test_secret", {"q": "键盘", "page_no": 1})
        assert p2["sign"] == sign1
        p3 = build_params("taobao.tbk.dg.material.optional",
                          "test_key", "test_secret", {"q": "键盘", "page_no": 2})
        assert p3["sign"] != sign1

    def test_mock_requires_no_key_and_fails_fast_in_taobao_mode(self):
        assert MallClient("mock").is_mock_mode
        with pytest.raises(RuntimeError):
            MallClient("taobao")  # 缺 AppKey 立即报错

    def test_mock_title_embeds_brand(self):
        mc = MallClient("mock")
        items = mc._mock("键盘", 1, 5)
        assert len(items) == 5
        assert all(i["title"] for i in items)


class TestSearchAPI:
    def test_search_returns_labelled_items(self, client):
        r = client.get("/api/search", params={"q": "键盘"})
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        items = data["items"]
        # mock 品牌全是种子 → 应都能打标
        assert all(i["rest_level"] is not None for i in items)
        assert all(i["company_name"] for i in items)
        # 双休优先排序：rest_level 非降序（None/99 排最后）
        keys = [i["rest_level"] or 6 for i in items]
        assert keys == sorted(keys)

    def test_filter_by_level(self, client):
        r = client.get("/api/search", params={"q": "手机", "level": 1})
        data = r.json()
        assert all(i["rest_level"] == 1 for i in data["items"])

    def test_indexed_only_filters_unknown(self, client):
        """indexed_only=true 应过滤 L6/未打标商品。"""
        r = client.get("/api/search", params={"q": "键盘", "indexed_only": "true"})
        items = r.json()["items"]
        assert all(i["rest_level"] not in (None, 6) for i in items)
        # 对照：不过滤时应包含 L6
        r2 = client.get("/api/search", params={"q": "键盘"})
        assert any(i["rest_level"] in (None, 6) for i in r2.json()["items"])

    def test_unknown_company_sorted_last(self, client):
        """模拟未映射品牌 → rest_level=None 应在列表末尾。"""
        from app.routers import search as search_mod

        original = search_mod.mall_client

        class FakeMall:
            async def search(self, kw, page_no=1, page_size=20):
                return [{"item_id": "x1", "title": "某杂牌企业 电动牙刷", "image": "",
                         "price": 99.0, "brand": "", "category": "", "click_url": ""}]
        search_mod.mall_client = FakeMall()
        try:
            r = client.get("/api/search", params={"q": "牙刷"})
            items = r.json()["items"]
            assert items[0]["rest_level"] is None
            assert items[0]["brand"] is None
        finally:
            search_mod.mall_client = original

    def test_company_level_from_db(self, client, engine):
        """设置一家公司等级，验证商品反映真实档案等级。"""
        from app.routers import search as search_mod

        proof = {}

        class FakeMall:
            async def search(self, kw, page_no=1, page_size=20):
                return [{"item_id": "x2", "title": "OPPO官方旗舰店 智能手表 促销",
                         "image": "", "price": 999.0, "brand": "", "category": "",
                         "click_url": ""}]
        with Session(engine) as s:
            # seed 里 OPPO → OPPO广东移动通信有限公司
            c = s.query(Company).filter(Company.name.like("%OPPO%")).first()
            c.level, c.confidence = 4, 0.9
            s.commit()
            proof["company_level"] = c.level
        original = search_mod.mall_client
        search_mod.mall_client = FakeMall()
        try:
            r = client.get("/api/search", params={"q": "手表"})
            item = r.json()["items"][0]
            assert item["rest_level"] == proof["company_level"]
            assert item["confidence"] == round(0.9, 3)
        finally:
            search_mod.mall_client = original