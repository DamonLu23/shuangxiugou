"""榜单名录采集 CLI：公开排行榜 → data/companies/seed_extra.csv。

流程：
    排行榜页面（静态 HTML） --解析--> 企业候选 --去重--> seed_extra.csv
    再由 expand_seed.py 幂等合并进 seed.csv（新企业默认 L6 待验证）

用法:
    .venv/bin/python fetch_lists.py --dry-run                # 预览新增（不写文件）
    .venv/bin/python fetch_lists.py                          # 写 seed_extra.csv
    .venv/bin/python fetch_lists.py --only fortune-china500  # 只跑某个榜单

去重规则（duplicate_reason）：同名企业 / 同 key / 中文品牌包含关系
（如「浙江吉利控股集团」被既有「吉利」覆盖则跳过）。
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sources.list_rankings import (  # noqa: E402
    LIST_SOURCES, derive_key, duplicate_reason,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "companies"
SEED = DATA_DIR / "seed.csv"
DEFAULT_OUT = DATA_DIR / "seed_extra.csv"
FIELDS = ["key", "full_name", "category"]
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")


def load_seed_index() -> tuple[dict[str, str], set[str]]:
    with open(SEED, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["key"]: r["full_name"] for r in rows}, {r["full_name"] for r in rows}


def fetch_html(url: str) -> str:
    with httpx.Client(headers={"User-Agent": UA}, timeout=30.0,
                      follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def collect(source_names: list[str], keys: dict, names: set) -> tuple[list[dict], dict]:
    """抓取并解析所选榜单，返回 (新增候选, 统计)。"""
    added, stats = [], {}
    seen_pairs = set()
    for name in source_names:
        cfg = LIST_SOURCES[name]
        try:
            html = fetch_html(cfg["url"])
            rows = cfg["parser"](html)
        except Exception as e:
            stats[name] = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}
            continue
        src_added, skip = 0, 0
        for r in rows:
            full_name = r["full_name"]
            key = derive_key(full_name)
            if not key or len(key) < 2 or (key, full_name) in seen_pairs:
                skip += 1
                continue
            reason = duplicate_reason(key, full_name, keys, names)
            if reason:
                skip += 1
                continue
            seen_pairs.add((key, full_name))
            keys[key] = full_name
            names.add(full_name)
            added.append({"key": key, "full_name": full_name, "category": ""})
            src_added += 1
        stats[name] = {"ok": True, "total": len(rows), "added": src_added, "skipped": skip}
    return added, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="逗号分隔的榜单名，默认全部")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    names = [n.strip() for n in args.only.split(",") if n.strip()] or list(LIST_SOURCES)
    unknown = [n for n in names if n not in LIST_SOURCES]
    if unknown:
        print(f"未知榜单: {unknown}（可选: {list(LIST_SOURCES)}）")
        sys.exit(2)

    keys, names_set = load_seed_index()
    seed_count = len(keys)
    print(f"[榜单] 现有种子 {seed_count} 家；本次榜单: {names}")

    added, stats = collect(names, keys, names_set)
    for name, st in stats.items():
        if st["ok"]:
            print(f"  - {name}: 榜单 {st['total']} 家 → 新增 {st['added']}，跳过 {st['skipped']}")
        else:
            print(f"  - {name}: 抓取失败（{st['error']}）")

    print(f"[榜单] 本次新增 {len(added)} 家（合并后 {seed_count + len(added)} 家）")
    for r in added[:15]:
        print(f"    + {r['key']} | {r['full_name']}")
    if len(added) > 15:
        print(f"    ... 其余 {len(added) - 15} 家见文件")

    if args.dry_run:
        print("[榜单] dry-run：未写文件")
        return
    out = Path(args.out)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(added)
    print(f"[榜单] 已写入 {out}")
    print("下一步: .venv/bin/python expand_seed.py（合并进 seed.csv）")


if __name__ == "__main__":
    main()
