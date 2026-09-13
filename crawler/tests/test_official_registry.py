"""官网岗位源测试：纯函数解析 / SPA 判定 / 配置与健康统计。"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import health as health_mod  # noqa: E402
from sources.official import (  # noqa: E402
    filter_job_anchors,
    is_spa_shell,
    parse_official_jobs,
)


class TestOfficialParser:
    def test_parse_server_rendered_html(self):
        html = """
        <html><body>
          <a href="/">首页</a>
          <a href="/login">登录</a>
          <a href="/about">关于我们</a>
          <a href="/job/detail/1001">高级后端工程师</a>
          <a href="/positions/sales-2026">销售经理</a>
          <a href="/product/detail/5">旗舰产品</a>
          <a href="javascript:void(0)">查看更多</a>
        </body></html>
        """
        jobs = parse_official_jobs(html, "https://careers.example.com")
        titles = [j["title"] for j in jobs]
        assert titles == ["高级后端工程师", "销售经理"]
        assert jobs[0]["url"] == "https://careers.example.com/job/detail/1001"

    def test_filter_anchors_excludes_content_pages(self):
        anchors = [
            {"title": "客服支持", "href": "/support/faq"},
            {"title": "产品详情", "href": "/product/detail/1"},
            {"title": "新闻中心", "href": "/news/1"},
            {"title": "运维开发工程师", "href": "/careers/job/9"},
        ]
        jobs = filter_job_anchors(anchors, "https://x.com")
        assert [j["title"] for j in jobs] == ["运维开发工程师"]

    def test_filter_anchors_dedup_and_limit(self):
        anchors = [
            {"title": "工程师A", "href": "/job/1"},
            {"title": "工程师A 重复", "href": "/job/1"},
            {"title": "工程师B", "href": "/job/2"},
        ]
        jobs = filter_job_anchors(anchors, "https://x.com", max_items=10)
        assert len(jobs) == 2

    def test_title_length_bounds(self):
        anchors = [
            {"title": "短", "href": "/job/a"},           # 太长 / 太短过滤
            {"title": "x" * 60, "href": "/job/b"},
            {"title": "正常岗位名", "href": "/job/c"},
        ]
        assert [j["title"] for j in filter_job_anchors(anchors, "https://x.com")] == ["正常岗位名"]

    def test_spa_shell_detection(self):
        assert is_spa_shell("<html><div id='app'></div></html>")
        assert not is_spa_shell(
            "<html>招聘 职位 岗位 " + "x" * 3000 + "</html>")


class TestRegistryConfig:
    def test_config_shape(self):
        from sources.registry import load_config
        cfg = load_config()
        assert cfg["evidence_sources"]["zhaopin"]["enabled"] is True
        assert cfg["job_sources"]["official"]["enabled"] is True
        assert cfg["politeness_seconds"] > 0

    def test_company_job_sources_csv(self):
        path = Path(__file__).resolve().parents[2] / "data" / "company_job_sources.csv"
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        assert len(rows) >= 14
        names = [r["company_name"] for r in rows]
        assert len(set(names)) == len(names), "企业不得重复"
        for r in rows:
            assert r["careers_url"].startswith("http")
            assert r["enabled"].lower() in ("true", "false")
            assert r["note"], "每家需注明当前状态"

    def test_load_company_job_sources_filters_enabled(self, tmp_path, monkeypatch):
        from sources import registry
        p = tmp_path / "cfg.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["company_name", "careers_url", "parser", "enabled", "note"])
            w.writerow(["甲公司", "https://a.com/jobs", "generic", "true", "ok"])
            w.writerow(["乙公司", "https://b.com/jobs", "generic", "false", "待适配"])
        monkeypatch.setattr(registry, "ROOT", tmp_path)
        rows = registry.load_company_job_sources("cfg.csv")
        assert [r["company_name"] for r in rows] == ["甲公司"]


class TestHealth:
    def test_report_written(self, tmp_path):
        h = health_mod.new_health()
        health_mod.record(h, "zhaopin", ok=True, items=12)
        health_mod.record(h, "zhaopin", ok=False)
        health_mod.record(h, "bing", ok=True, items=5)
        md = tmp_path / "health.md"
        js = tmp_path / "health.json"
        health_mod.write_report(h, md, js)
        text = md.read_text(encoding="utf-8")
        assert "| zhaopin | 1 | 1 | 12 |" in text
        assert "| bing | 1 | 0 | 5 |" in text
        import json as jsonlib
        data = jsonlib.loads(js.read_text(encoding="utf-8"))
        assert data["sources"]["zhaopin"]["items"] == 12