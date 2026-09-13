"""品牌→企业映射导入（seed.csv → brands / companies 表）。

品牌表用途：白名单企业的招聘检索品牌 key（crawler/collect_jobs.py 消费）。
"""

import csv
from pathlib import Path
from typing import Iterable

SEED_CSV = Path(__file__).resolve().parents[3] / "data" / "companies" / "seed.csv"


def normalize_brand(s: str) -> str:
    return s.replace(" ", "").upper()


def iter_seed_rows() -> Iterable[dict]:
    with open(SEED_CSV, encoding="utf-8") as f:
        yield from csv.DictReader(f)


def import_seed(session) -> int:
    """导入 seed.csv → brands / companies 表（幂等）。返回新增品牌条数。"""
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
            brand = Brand(name=row["key"], normalized_name=norm, aliases="",
                          company_id=company.id, verified=False)
            session.add(brand)
            n += 1
    session.commit()
    return n