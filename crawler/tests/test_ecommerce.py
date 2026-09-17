"""电商商品候选单测（纯函数，不触网）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sources.suning import (  # noqa: E402
    clean_title, filter_candidates, guess_category, is_accessory, parse_suning_results,
)


class TestCleanTitle:
    def test_removes_promo_brackets_and_tags(self):
        assert clean_title("【自营】苏泊尔<span>电饭煲</span> 4L 家用") == "苏泊尔电饭煲 4L 家用"

    def test_drops_hidden_em_selling_points(self):
        assert clean_title("苏泊尔电饭煲<em>预约、蒸煮、保温</em> 4L") == "苏泊尔电饭煲 4L"

    def test_collapses_whitespace(self):
        assert clean_title("海尔  冰箱\n双门") == "海尔 冰箱 双门"

    def test_truncates_long_title(self):
        assert len(clean_title("长" * 200)) == 80


class TestAccessoryAndCategory:
    def test_accessory_detected(self):
        assert is_accessory("适用华为P60手机壳")
        assert is_accessory("小米钢化膜 2片装")
        assert not is_accessory("华为Mate60 Pro 手机")

    def test_category_guess(self):
        assert guess_category("苏泊尔电饭煲4L") == "厨房家电"
        assert guess_category("海尔双门冰箱") == "家电"
        assert guess_category("伊利纯牛奶整箱") == "食品饮料"
        assert guess_category("神秘商品") == ""


class TestFilterCandidates:
    ITEMS = [
        {"sku": "1", "title": "【自营】苏泊尔电饭煲 4L", "shop": "自营店"},
        {"sku": "2", "title": "苏泊尔破壁机 家用", "shop": "官方旗舰店"},
        {"sku": "3", "title": "适用苏泊尔电饭煲内胆配件", "shop": "XX配件店"},   # 配件过滤
        {"sku": "4", "title": "美的电饭煲 4L", "shop": "美的旗舰店"},           # 非本品牌
        {"sku": "5", "title": "苏泊尔电饭煲 4L", "shop": "另一家店"},           # 不同 SKU，保留
        {"sku": "6", "title": "苏泊尔", "shop": "x"},                            # 过短
    ]

    def test_filters_and_dedupes(self):
        got = filter_candidates(self.ITEMS, "苏泊尔")
        titles = [g["product"] for g in got]
        assert "苏泊尔电饭煲 4L" in titles
        assert all("适用" not in t for t in titles)
        assert all("美的" not in t for t in titles)
        assert len(got) == 3

    def test_max_items_limit(self):
        items = [{"sku": str(i), "title": f"苏泊尔锅具{i}", "shop": "s"} for i in range(30)]
        assert len(filter_candidates(items, "苏泊尔", max_items=5)) == 5

    def test_ascii_brand_case_insensitive(self):
        items = [{"sku": "1", "title": "oppo Find X9 手机", "shop": "OPPO"}]
        assert len(filter_candidates(items, "OPPO")) == 1


SUNING_HTML = """
<html><body>
<div class="res-info"><div class="title-selling-point">
<a href="//product.suning.com/0000000000/11263308594.html">苏泊尔(SUPOR)电饭煲家用5L大容量<em style="display:none">隐藏卖点</em></a>
</div></div>
<div class="res-info"><div class="title-selling-point">
<a href="//product.suning.com/0000000000/22222222222.html">苏泊尔破壁机 家用多功能</a>
</div></div>
<div class="res-info"><div class="title-selling-point">
<a href="//product.suning.com/0000000000/33333333333.html">适用苏泊尔电饭煲内胆配件</a>
</div></div>
<div class="res-info"><div class="title-selling-point">
<a href="//product.suning.com/0000000000/44444444444.html">美的电饭煲 4L</a>
</div></div>
</body></html>
"""


class TestParseSuning:
    def test_extracts_brand_products_with_sku(self):
        got = parse_suning_results(SUNING_HTML, "苏泊尔")
        assert [g["sku"] for g in got] == ["11263308594", "22222222222"]
        assert "隐藏卖点" not in got[0]["product"]
        assert "电饭煲家用5L大容量" in got[0]["product"]
        assert got[0]["category"] == "厨房家电"

    def test_non_matching_brand_returns_empty(self):
        assert parse_suning_results(SUNING_HTML, "格力") == []

    def test_empty_html(self):
        assert parse_suning_results("<html></html>", "苏泊尔") == []
