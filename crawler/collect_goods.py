"""电商商品候选采集：白名单品牌 → data/goods_candidates.csv（人工确认制）。

数据源：苏宁易购搜索页（静态 HTML，httpx 直取；京东已登录墙，见 docs/sources.md）。

流程：
    白名单（L1/L2）品牌 key --苏宁搜索--> 候选商品（标题/SKU/品类猜测）
    → 人工挑选代表商品 + 补官网/官方旗舰店链接 → 追加 data/goods.csv

注意：产物不含任何电商链接/价格（用户定调：只抓信息，不放链接）。

用法:
    .venv/bin/python collect_goods.py --dry-run          # 预览候选（不写文件）
    .venv/bin/python collect_goods.py                    # 写 goods_candidates.csv
    .venv/bin/python collect_goods.py --limit 2          # 只跑前 2 家白名单企业
"""

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from collect_jobs import whitelist_companies  # noqa: E402
from health import new_health, record, write_report  # noqa: E402
from sources.suning import SuningGoodsSource  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "goods_candidates.csv"
FIELDS = ["company_name", "brand", "category", "product", "shop", "sku", "note"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 家白名单企业")
    ap.add_argument("--max-per-brand", type=int, default=10, help="每品牌候选上限")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--politeness", type=float, default=2.0)
    args = ap.parse_args()

    companies = whitelist_companies(args.limit)
    print(f"[商品候选] 白名单企业 {len(companies)} 家（苏宁搜索，人工确认制）")

    src = SuningGoodsSource()
    health = new_health()
    rows: list[dict] = []
    for i, (company, brand_key) in enumerate(companies, 1):
        got = src.fetch_candidates(brand_key, args.max_per_brand)
        record(health, "suning", ok=True, items=len(got))
        rows += [{
            "company_name": company.name,
            "brand": brand_key,
            "category": g["category"],
            "product": g["product"],
            "shop": g["shop"],
            "sku": g["sku"],
            "note": "",
        } for g in got]
        print(f"  [{i}/{len(companies)}] {company.name}: 候选 {len(got)} 条")
        if i < len(companies):
            time.sleep(args.politeness)

    write_report(health, ROOT / "data" / "source_health_goods.md")

    if args.dry_run:
        print(f"[商品候选] dry-run：{len(rows)} 条，未写文件")
        for r in rows[:10]:
            print(f"    - {r['brand']} | {r['product'][:40]} | {r['category']}")
        return

    out = Path(args.out)
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[商品候选] 已写入 {out}（{len(rows)} 条）")
    print("下一步: 人工挑选代表商品，补 category/official_link 后追加 data/goods.csv")


if __name__ == "__main__":
    main()
