"""采集源注册表：从 sources_config.json 构建启用中的源（替代硬编码）。

用法:
    from sources.registry import load_config, make_evidence_sources, make_job_sources
    cfg = load_config()
    sources = make_evidence_sources(cfg)   # [(name, Source), ...]
"""

import csv
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "sources_config.json"
ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_evidence_sources(cfg: dict) -> list[tuple]:
    """构建启用中的证据源：[(name, source_instance), ...]"""
    from sources.bing_snippet import BingSnippetSource
    from sources.zhaopin import ZhaopinSource

    out = []
    z = cfg.get("evidence_sources", {}).get("zhaopin", {})
    if z.get("enabled"):
        out.append(("zhaopin", ZhaopinSource(city_id=z.get("city_id", ""))))
    b = cfg.get("evidence_sources", {}).get("bing", {})
    if b.get("enabled"):
        out.append(("bing", BingSnippetSource()))
    return out


def load_company_job_sources(csv_path: str = "data/company_job_sources.csv") -> list[dict]:
    """读取官网岗位配置（仅 enabled=true 的企业参与采集）。"""
    path = ROOT / csv_path
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [
        r for r in rows
        if r.get("company_name") and r.get("careers_url")
        and (r.get("enabled", "").strip().lower() == "true")
    ]


def make_job_sources(cfg: dict, browser=None) -> list[tuple]:
    """构建启用中的岗位源：[(name, source_instance, options), ...]"""
    from sources.official import OfficialJobsSource
    from sources.zhaopin import ZhaopinSource

    out = []
    z = cfg.get("job_sources", {}).get("zhaopin", {})
    if z.get("enabled"):
        out.append(("zhaopin", ZhaopinSource(city_id=z.get("city_id", "")), {}))
    o = cfg.get("job_sources", {}).get("official", {})
    if o.get("enabled"):
        official = OfficialJobsSource(browser)
        companies = load_company_job_sources(o.get("config_csv", "data/company_job_sources.csv"))
        out.append(("official", official, {"companies": companies}))
    return out