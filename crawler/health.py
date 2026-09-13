"""采集源健康统计：每源成功/失败/条目数 → 周更报告（CI PR 正文）。"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HealthDict = dict


def new_health() -> HealthDict:
    return defaultdict(lambda: {"ok": 0, "fail": 0, "items": 0})


def record(health: HealthDict, source: str, ok: bool, items: int = 0):
    health[source]["ok" if ok else "fail"] += 1
    health[source]["items"] += items


def write_report(health: HealthDict, md_path: Path, json_path: Path = None):
    """写 markdown 报告（可作 CI PR 正文）与 JSON。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "自动生成的数据更新 PR，由维护者人工抽查后合并。",
        "",
        f"数据时间：{now}",
        "",
        "| 源 | 成功 | 失败 | 条目 |",
        "|---|---|---|---|",
    ]
    for src, h in sorted(health.items()):
        lines.append(f"| {src} | {h['ok']} | {h['fail']} | {h['items']} |")
    lines += [
        "",
        "检查点：白名单数量是否合理、等级分布是否突变、证据链接是否有效、",
        "本地版 bundle（web/local/dist）是否同步更新。",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({
            "generated_at": now,
            "sources": {k: dict(v) for k, v in health.items()},
        }, ensure_ascii=False, indent=1), encoding="utf-8")