import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.levels import aggregate, score_to_level, time_decay
from crawler.normalize import match_key, normalize_company
from crawler.scoring.keywords import score_job_description
import pytest


class TestKeywords:
    def test_strict_double_rest(self):
        score, kws = score_job_description("周末双休，朝九晚五")
        assert score >= 2.0
        assert "周末双休" in kws
        assert score > 0

    def test_single_rest(self):
        score, kws = score_job_description("做六休一，单休")
        assert score <= -2.0
        assert "单休" in kws

    def test_996(self):
        score, kws = score_job_description("大小周，偶尔996")
        assert "996" in kws or score <= -3.0

    def test_mixed_negative_wins(self):
        score, _ = score_job_description("周末双休，但大小周轮换，偶尔996")
        assert score < 0

    def test_plain_rest_less_than_official(self):
        plain, _ = score_job_description("双休")
        fast, _ = score_job_description("五天八小时")
        assert fast > plain

    def test_no_overtime_not_penalized(self):
        score, kws = score_job_description("周末双休，不加班，朝九晚六")
        assert "加班" not in kws
        assert score > 0


class TestNormalize:
    def test_strip_subsidiary(self):
        assert normalize_company("华为技术有限公司北京研究所") == "华为技术有限公司北京"

    def test_match_key_ok(self):
        assert match_key("华为技术有限公司北京研究所", "华为")
        assert match_key("海尔智家股份有限公司", "海尔")

    def test_match_key_reject(self):
        assert not match_key("新疆华为商贸有限公司", "华为")
        assert not match_key("北京小米股权投资基金管理有限公司", "小米")


class TestAggregate:
    def test_single_job_post(self):
        level, conf = aggregate([{
            "raw_score": 3.5, "source_type": "job_post",
            "collected_at": date.today(),
        }])
        assert level == 1
        assert 0 < conf < 1

    def test_contradiction_becomes_unknown(self):
        level, conf = aggregate([], disputed=True)
        assert level == 6 and conf == 0.0

    def test_time_decay(self):
        old = date.today() - timedelta(days=400)
        fresh = date.today()
        assert time_decay(old) < time_decay(fresh)

    def test_strong_996(self):
        level, _ = aggregate([{
            "raw_score": -3.0, "source_type": "ugc_contract",
            "collected_at": date.today(),
        }])
        assert level == 5