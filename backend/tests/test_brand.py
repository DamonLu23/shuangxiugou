"""品牌→企业映射导入测试（seed.csv → brands/companies 表）。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Brand, Company
from app.services.brand import import_seed, normalize_brand


def _seed_engine():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    return e


def test_normalize_brand():
    assert normalize_brand(" op po ") == "OPPO"


def test_import_seed_populates_and_idempotent():
    e = _seed_engine()
    with Session(e) as s:
        import_seed(s)
        brands = s.query(Brand).count()
        companies = s.query(Company).count()
        assert brands >= 200
        assert companies >= 200
        import_seed(s)  # 二次导入幂等
        assert s.query(Brand).count() == brands
        assert s.query(Company).count() == companies


def test_seed_company_defaults_to_l6():
    e = _seed_engine()
    with Session(e) as s:
        import_seed(s)
        untested = s.query(Company).filter(Company.level == 6).count()
        assert untested >= 200  # 新导入企业默认待验证