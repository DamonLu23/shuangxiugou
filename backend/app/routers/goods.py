"""好物目录 API：data/goods.csv（社区 PR 维护），仅展示白名单企业商品。"""

import csv
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Company
from ..db.session import get_db

router = APIRouter(prefix="/api")

GOODS_CSV = Path(__file__).resolve().parents[3] / "data" / "goods.csv"


def _load_goods() -> list[dict]:
    if not GOODS_CSV.exists():
        return []
    with open(GOODS_CSV, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("product")]


@router.get("/goods/search")
async def goods_search(
    q: str = Query(..., min_length=1, description="品类/商品关键词，如 咖啡/键盘/寄件"),
    db: Session = Depends(get_db),
):
    """搜索好物目录：只返回白名单（L1/L2）企业的商品。"""
    rows = _load_goods()
    if not rows:
        return {"query": q, "total": 0, "items": []}

    whitelist_map = {
        c.name: (c.level, c.confidence)
        for c in db.scalars(select(Company)).all()
        if c.level in (1, 2)
    }
    whitelist_names = set(whitelist_map)

    items = []
    for r in rows:
        name = r.get("company_name", "")
        if name not in whitelist_names:
            continue  # 白名单承诺：非 L1/L2 企业的商品不展示
        haystack = f"{r.get('category', '')} {r.get('product', '')}"
        if q.lower() not in haystack.lower():
            continue
        level, conf = whitelist_map[name]
        items.append({
            "company_name": name,
            "company_level": level,
            "category": r.get("category", ""),
            "product": r.get("product", ""),
            "official_link": r.get("official_link", ""),
            "note": r.get("note", ""),
        })
    return {"query": q, "total": len(items), "items": items}