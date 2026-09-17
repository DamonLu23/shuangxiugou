"""榜单名录解析单测（纯函数，不触网）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sources.list_rankings import (  # noqa: E402
    cn_name, derive_key, duplicate_reason, is_cjk_key,
    parse_cnenterprise500, parse_fortune_china500, parse_fortune_global500,
    parse_plain_ranked_table, parse_ranked_table,
)

GLOBAL500_HTML = """
<html><body><table id="table1" class="wt-table">
<thead><tr><th>排名</th><th>公司名称</th><th>营收</th><th>利润</th><th>国家</th><th>关键</th></tr></thead>
<tbody>
<tr><td>1</td><td><a href="../../global500/485/2026">亚马逊（AMAZON.COM) </a> </td><td>716,924</td><td>77,670</td><td>美国</td><td class="control"><span>+</span></td></tr>
<tr><td>3</td><td><a href="../../global500/15/2026">国家电网有限公司（STATE GRID) </a> </td><td>555,371.4</td><td>11,116.2</td><td>中国</td><td class="control"><span>+</span></td></tr>
<tr><td>11</td><td><a href="#">京东集团股份有限公司（JD.COM) </a> </td><td>161,055.4</td><td>5,748.2</td><td>中国</td><td class="control"><span>+</span></td></tr>
</tbody></table></body></html>
"""

CN500_HTML = """
<html><body><table id="table1" class="wt-table">
<thead><tr><th>排名</th><th>上年</th><th>公司名称</th><th>营收</th><th>利润</th><th>关键</th></tr></thead>
<tbody>
<tr><td>1</td><td>1</td><td><a href="#">国家电网有限公司</a> </td><td>555,371.4</td><td>11,116.2</td><td class="control"><span>+</span></td></tr>
<tr><td>13</td><td>14</td><td><a href="#">中国平安保险（集团）股份有限公司</a> </td><td>158,627</td><td>17,596.1</td><td class="control"><span>+</span></td></tr>
<tr><td>合计</td><td>-</td><td><a href="#">汇总行</a></td><td>-</td><td>-</td><td class="control"></td></tr>
</tbody></table></body></html>
"""


class TestParseFortune:
    def test_global500_filters_non_china_and_strips_english(self):
        rows = parse_fortune_global500(GLOBAL500_HTML)
        assert [r["full_name"] for r in rows] == ["国家电网有限公司", "京东集团股份有限公司"]

    def test_global500_rank_kept(self):
        rows = parse_fortune_global500(GLOBAL500_HTML)
        assert rows[0]["rank"] == 3

    def test_china500_keeps_chinese_parens(self):
        rows = parse_fortune_china500(CN500_HTML)
        assert [r["full_name"] for r in rows] == [
            "国家电网有限公司", "中国平安保险（集团）股份有限公司"]
        assert len(rows) == 2  # 非数字排名行（汇总）被跳过

    def test_missing_table_returns_empty(self):
        assert parse_ranked_table("<html>无表格</html>") == []
        assert parse_fortune_china500("<html>无表格</html>") == []


class TestParsePlainRankedTable:
    def _table(self, rows: int) -> str:
        body = "".join(
            f"<tr><td>{i}</td><td>示例企业{i}有限公司</td><td>{i}00</td></tr>"
            for i in range(1, rows + 1)
        )
        return ("<html><body><table><tr><td>名次</td><td>企业名称</td>"
                f"<td>营业收入/万元</td></tr>{body}</table></body></html>")

    def test_parses_min_rows_table(self):
        rows = parse_plain_ranked_table(self._table(120), min_rows=100)
        assert len(rows) == 120
        assert rows[0]["name"] == "示例企业1有限公司"

    def test_rejects_small_or_headerless_tables(self):
        assert parse_plain_ranked_table(self._table(50), min_rows=100) == []
        assert parse_plain_ranked_table("<table><tr><td>1</td><td>x</td></tr></table>",
                                        min_rows=1) == []

    def test_cnenterprise500_wrapper(self):
        rows = parse_cnenterprise500(self._table(150))
        assert len(rows) == 150
        assert rows[-1]["rank"] == 150


class TestCnName:
    def test_strip_english_paren(self):
        assert cn_name("亚马逊（AMAZON.COM) ") == "亚马逊"

    def test_keep_chinese_paren(self):
        assert cn_name("中国平安保险（集团）股份有限公司") == "中国平安保险（集团）股份有限公司"

    def test_all_english_fallback(self):
        assert cn_name("（AMAZON)") == "（AMAZON)"


class TestDeriveKey:
    def test_plain(self):
        assert derive_key("国家电网有限公司") == "国家电网"

    def test_strip_multiple_suffixes(self):
        assert derive_key("阿里巴巴集团控股有限公司") == "阿里巴巴"
        assert derive_key("华为投资控股有限公司") == "华为投资"
        assert derive_key("中国石油天然气集团有限公司") == "中国石油天然气"

    def test_strip_chinese_parens(self):
        assert derive_key("中国平安保险（集团）股份有限公司") == "中国平安保险"

    def test_no_suffix(self):
        assert derive_key("台积公司") == "台积"


class TestDuplicateReason:
    def test_same_full_name(self):
        assert duplicate_reason("华为投资", "华为技术有限公司",
                                {"华为": "华为技术有限公司"}, {"华为技术有限公司"}) == "已有同名企业"

    def test_same_key(self):
        assert duplicate_reason("京东", "京东集团股份有限公司",
                                {"京东": "北京京东世纪贸易有限公司"}, set()) == "已有同 key"

    def test_cjk_substring(self):
        assert "吉利" in duplicate_reason("浙江吉利控股", "浙江吉利控股集团有限公司",
                                          {"吉利": "浙江吉利控股集团有限公司"}, set())

    def test_ascii_key_no_substring_false_positive(self):
        assert duplicate_reason("TCL科技", "TCL科技集团股份有限公司",
                                {"TCL": "TCL科技集团股份有限公司"}, set()) is None

    def test_unrelated_not_duplicate(self):
        assert duplicate_reason("中国石油化工", "中国石油化工集团有限公司",
                                {"中国石油天然气": "中国石油天然气集团有限公司"}, set()) is None

    def test_is_cjk_key(self):
        assert is_cjk_key("华为")
        assert not is_cjk_key("TCL")
        assert not is_cjk_key("OPPO广东")
        assert not is_cjk_key("")
