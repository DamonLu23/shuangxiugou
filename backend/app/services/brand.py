"""品牌→企业映射：seed.csv 导入 + 商品标题品牌识别。

- 归一化：去空白、统一大写（中文不受影响）
- 识别：在标题做最长匹配（已知品牌库），避免 OPPO/OPPO 等短词错分
"""

import csv
from pathlib import Path
from typing import Iterable, Optional

SEED_CSV = Path(__file__).resolve().parents[3] / "data" / "companies" / "seed.csv"


def normalize_brand(s: str) -> str:
    return s.replace(" ", "").upper()


def iter_seed_rows() -> Iterable[dict]:
    with open(SEED_CSV, encoding="utf-8") as f:
        yield from csv.DictReader(f)


def import_seed(session) -> int:
    """导入 seed.csv → brands / companies 表（幂等）。返回品牌条数。"""
    from ..db.models import Brand, Company

    n = 0
    for row in iter_seed_rows():
        company = session.query(Company).filter(Company.name == row["full_name"]).first()
        if not company:
            company = Company(name=row["full_name"], level=6, confidence=0.0)
            session.add(company)
            session.flush()
        if not row["key"]:
            continue
        norm = normalize_brand(row["key"])
        brand = session.query(Brand).filter(Brand.normalized_name == norm).first()
        if not brand:
            brand = Brand(name=row["key"], normalized_name=norm, aliases="", company_id=company.id, verified=False)
            session.add(brand)
            n += 1
    session.commit()
    return n


def build_lookup(session) -> dict:
    """normalized 品牌 → Brand 行 的查找表（标题识别用）。"""
    from ..db.models import Brand

    return {b.normalized_name: b for b in session.query(Brand).all()}


def extract_brand(title: str, lookup: Optional[dict] = None,
                  brand_field: str = "") -> Optional[str]:
    """从商品标题提取品牌名（最长匹配优先；其次品牌字段；再无则 None）。"""
    if brand_field and brand_field.strip():
        cand = normalize_brand(brand_field)
        if lookup and cand in lookup:
            return lookup[cand].name
        return brand_field.strip()

    if lookup:
        norm_title = normalize_brand(title)
        best, best_len = None, -1
        for norm, b in lookup.items():
            if norm in norm_title and len(norm) > best_len:
                best, best_len = b.name, len(norm)
        if best:
            return best
    return None