"""采集源解析纯函数单测（不触网）。

覆盖：Bing SERP 解析（黑名单/问句/员工平台分类）、智联城市提取。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sources.bing_snippet import parse_bing_results
from sources.zhaopin import extract_city


def _serp(*items: str) -> str:
    body = "".join(
        f'<li class="b_algo"><h2><a href="{u}">{t}</a></h2><p>{b}</p></li>'
        for u, t, b in items
    )
    return f"<html><body><ol>{body}</ol></body></html>"


class TestParseBing:
    def test_employee_host_review_positive(self):
        html = _serp(
            ("https://www.zhihu.com/question/1", "华为工作体验分享",
             "在华为工作周末双休，朝九晚六很舒服"))
        evs = parse_bing_results(html, "华为")
        assert len(evs) == 1
        assert evs[0].source_type == "review"
        assert evs[0].raw_score > 0

    def test_promo_host_classified(self):
        html = _serp(
            ("https://aiqicha.baidu.com/x", "华为简介",
             "华为提供周末双休福利待遇好"))
        evs = parse_bing_results(html, "华为")
        assert len(evs) == 1
        assert evs[0].source_type == "review_promo"

    def test_denylist_dropped(self):
        html = _serp(
            ("https://baike.baidu.com/item/x", "华为公司",
             "华为的996工作制争议很多"))
        assert parse_bing_results(html, "华为") == []

    def test_question_title_scores_snippet_only(self):
        """问句标题「双休吗」不作为正信号；正文未答 → 无证据。"""
        html = _serp(
            ("https://www.zhihu.com/question/2", "华为周末双休吗？",
             "想知道华为的作息安排，有人了解吗"))
        assert parse_bing_results(html, "华为") == []

    def test_question_title_with_positive_snippet(self):
        """问句标题 + 正文明确回答 → 按正文打分为正。"""
        html = _serp(
            ("https://www.nowcoder.com/feed/3", "顺丰有双休吗？",
             "有的，顺丰总部周末双休，做五休二"))
        evs = parse_bing_results(html, "顺丰")
        assert len(evs) == 1
        assert evs[0].raw_score > 0

    def test_off_topic_company_dropped(self):
        """正文不含公司名（仅标题含）且标题为问句 → 丢弃。"""
        html = _serp(
            ("https://www.zhihu.com/question/4", "华为怎么样？",
             "朋友想换工作，大家有什么建议"))
        assert parse_bing_results(html, "华为") == []

    def test_no_signal_dropped(self):
        html = _serp(
            ("https://www.zhihu.com/question/5", "华为发布会",
             "华为发布了新款手机，配置很强"))
        assert parse_bing_results(html, "华为") == []


class TestExtractCity:
    def test_common_city(self):
        assert extract_city("急招普工 4000-5000元 西安 经验不限 高中") == "西安"
        assert extract_city("结构开发工程师 8000-11000元 苏州 1-3年 本科") == "苏州"

    def test_endswith_city(self):
        assert extract_city("后端工程师 15-25K 杭州") == "杭州"

    def test_fallback_when_unknown(self):
        assert extract_city("远程办公 岗位描述", fallback="未知") == "未知"
        assert extract_city("", fallback="") == ""

    def test_city_priority_first_match(self):
        # 多城市文本取首个命中
        text = "北京 上海 双城招聘 工程师"
        assert extract_city(text) == "北京"
