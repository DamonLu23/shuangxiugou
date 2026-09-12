"""品牌扩编工具：把 seed_extra.csv 的新品牌并入 seed.csv（REVIEW P2：202 → 1000+ 路径）。

用法:
    .venv/bin/python expand_seed.py                # 合并 data/companies/seed_extra.csv
    .venv/bin/python expand_seed.py --dry-run      # 只预览

规则：
- 按 key 去重（大小写敏感，与 seed.csv 一致）
- full_name 为常用企业名，允许与工商注册名有出入（L6 待验证 + 纠错流程兜底）
- 新增企业档案等级默认 L6，由采集管线/UGC 逐步填充
"""

import argparse
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "companies"
SEED = DATA_DIR / "seed.csv"
EXTRA = DATA_DIR / "seed_extra.csv"
FIELDS = ["key", "full_name", "category"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(SEED, encoding="utf-8") as f:
        existing = list(csv.DictReader(f))
    known_keys = {r["key"] for r in existing}
    known_names = {r["full_name"] for r in existing}

    with open(EXTRA, encoding="utf-8") as f:
        extra = list(csv.DictReader(f))

    added, skipped = [], []
    for r in extra:
        if r["key"] in known_keys or r["full_name"] in known_names:
            skipped.append(r["key"])
            continue
        known_keys.add(r["key"])
        known_names.add(r["full_name"])
        added.append({k: r.get(k, "") for k in FIELDS})

    print(f"新增 {len(added)} 家，跳过重复 {len(skipped)} 家: {skipped or '无'}")
    if args.dry_run:
        for r in added[:10]:
            print("  +", r["key"], "|", r["full_name"], "|", r["category"])
        return

    with open(SEED, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerows(added)
    print(f"已追加到 {SEED}（现共 {len(existing) + len(added)} 家）")
    print("下一步: backend 导入品牌映射 → .venv/bin/python -c \"...import_seed(session)\"")


if __name__ == "__main__":
    main()