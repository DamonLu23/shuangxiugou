"""好物子系统测试：目录搜索 + 白名单过滤。"""

import csv

from app.routers import goods as goods_mod


def _write_goods(tmp_path, rows):
    csv_path = tmp_path / "goods.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company_name", "category", "product", "official_link", "note"])
        w.writerows(rows)
    return csv_path


class TestGoodsSearch:
    def test_whitelist_only(self, client, seed_companies, tmp_path, monkeypatch):
        csv_path = _write_goods(tmp_path, [
            ["双休科技股份有限公司", "互联网", "双休云服务", "https://sxg.io", ""],
            ["单休制造股份有限公司", "制造", "单休机床", "https://dx.io", ""],
            ["待验证商贸股份有限公司", "贸易", "待验证货品", "https://dz.io", ""],
        ])
        monkeypatch.setattr(goods_mod, "GOODS_CSV", csv_path)

        r = client.get("/api/goods/search", params={"q": "云"})
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["company_name"] == "双休科技股份有限公司"
        assert items[0]["company_level"] == 1

        # 非白名单商品即使关键词命中也不可见
        assert client.get("/api/goods/search", params={"q": "机床"}).json()["total"] == 0
        assert client.get("/api/goods/search", params={"q": "货品"}).json()["total"] == 0

    def test_category_match(self, client, seed_companies, tmp_path, monkeypatch):
        csv_path = _write_goods(tmp_path, [
            ["双休科技股份有限公司", "厨房家电", "破壁机", "https://x.io", ""],
        ])
        monkeypatch.setattr(goods_mod, "GOODS_CSV", csv_path)
        assert client.get("/api/goods/search", params={"q": "家电"}).json()["total"] == 1
        assert client.get("/api/goods/search", params={"q": "手机"}).json()["total"] == 0

    def test_missing_csv_returns_empty(self, client, seed_companies, tmp_path, monkeypatch):
        monkeypatch.setattr(goods_mod, "GOODS_CSV", tmp_path / "none.csv")
        assert client.get("/api/goods/search", params={"q": "任意"}).json()["total"] == 0