from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db.models import Company, LEVEL_NAMES
from ..db.session import get_db
from ..services.brand import build_lookup, extract_brand, normalize_brand
from ..services.mall import mall_client

router = APIRouter(prefix="/api")


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    level: Optional[int] = Query(None, ge=1, le=6),
    sort: str = Query("rest_first"),
    page: int = Query(1, ge=1),
    indexed_only: bool = Query(False, description="只看已收录双休档案的商品"),
    db: Session = Depends(get_db),
):
    """商品搜索：联盟搜索 → 标题提取品牌 → 企业双休等级打标 → 排序。

    sort=rest_first（默认）：L1 严格双休在前、L2 次之，未收录企业（L6/无档案）在后。
    indexed_only=true 过滤掉未收录（L6/无档案）商品。
    """
    items = await mall_client.search(q, page_no=page)
    if not items:
        return {"query": q, "sort": sort, "total": 0, "items": []}

    lookup = build_lookup(db)
    results = []
    for it in items:
        brand = extract_brand(it.get("title", ""), lookup, it.get("brand", ""))
        company_id = company_name = rest_level = confidence = None
        if brand:
            b = lookup.get(normalize_brand(brand))
            if b:
                company = db.get(Company, b.company_id)
                if company:
                    company_id, company_name = company.id, company.name
                    rest_level, confidence = company.level, company.confidence
        results.append({
            **it,
            "brand": brand,
            "company_id": company_id,
            "company_name": company_name,
            "rest_level": rest_level,
            "rest_level_name": LEVEL_NAMES.get(rest_level, "待验证") if rest_level else None,
            "confidence": round(confidence, 3) if confidence is not None else None,
        })

    if sort == "rest_first":
        results.sort(key=lambda r: _rank(r.get("rest_level")))
    elif sort == "price_asc":
        results.sort(key=lambda r: r.get("price") or 0)
    elif sort == "price_desc":
        results.sort(key=lambda r: -(r.get("price") or 0))

    if level:
        results = [r for r in results if r.get("rest_level") == level]
    if indexed_only:
        results = [r for r in results if r.get("rest_level") not in (None, 6)]

    return {"query": q, "sort": sort, "total": len(results), "items": results}


def _rank(level: Optional[int]) -> int:
    """双休优先排序键：L1=0 最优，L6/无档案=99 最后。"""
    if level is None:
        return 99
    return level - 1