"""verify.py 校验逻辑测试：达标数据通过 / 不达标数据 exit(1)。"""

import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import verify  # noqa: E402
from app.db.models import Base, Company, Evidence  # noqa: E402


def _make_db(passing: bool) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    e = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        # 达线：105 家公司，其中 45 家有证据；L1/L2 各 10 家且 ≥2 条证据
        for i in range(105):
            s.add(Company(name=f"公司{i}", level=6, confidence=0.0))
        s.flush()
        rows = s.query(Company).all()
        n_ev = 45 if passing else 10
        for i, c in enumerate(rows[:n_ev]):
            lv = 1 if i < 10 else 4
            c.level, c.confidence = lv, 0.5
            s.add(Evidence(company_id=c.id, source_type="review",
                           url=f"https://x/{i}/1", keywords="双休", raw_score=1.5,
                           weight=0.9, collected_at=date.today(), reviewed=False))
            if passing and i < 10:
                s.add(Evidence(company_id=c.id, source_type="review",
                               url=f"https://x/{i}/2", keywords="双休", raw_score=1.5,
                               weight=0.9, collected_at=date.today(), reviewed=False))
        if not passing:
            # 制造越界数据：置信度 1.5
            rows[0].confidence = 1.5
        s.commit()
    return Path(tmp.name)


@pytest.fixture(autouse=True)
def _clean_failures():
    verify.failures.clear()
    yield
    verify.failures.clear()


def test_verify_passes_on_good_data(monkeypatch):
    monkeypatch.setattr(verify, "DB_PATH", _make_db(passing=True))
    verify.main()  # 不应抛 SystemExit
    assert verify.failures == []


def test_verify_fails_on_bad_data(monkeypatch):
    monkeypatch.setattr(verify, "DB_PATH", _make_db(passing=False))
    with pytest.raises(SystemExit) as exc:
        verify.main()
    assert exc.value.code == 1
    assert len(verify.failures) > 0  # 档案不足 + 置信度越界 + 交叉验证不足