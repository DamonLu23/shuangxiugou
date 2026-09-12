"""采集源解析纯函数单测（不触网）。

覆盖 REVIEW P3：Bing SERP 解析（黑名单/问句/员工平台分类）。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sources.bing_snippet import parse_bing_results


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
