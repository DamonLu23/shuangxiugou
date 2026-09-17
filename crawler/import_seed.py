"""种子企业导入脚本：把 seed.csv 的全部企业/品牌写入 DB（幂等）。

用途：
- 榜单扩编（fetch_lists.py + expand_seed.py）后，让新企业进入 DB（默认 L6），
  供 pipeline 证据采集/collect_jobs 品牌检索使用
- backend 启动时也会自动执行（main.py lifespan），此脚本供离线批量场景

用法:
    .venv/bin/python import_seed.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.services.brand import import_seed  # noqa: E402


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        added = import_seed(db)
    print(f"[种子导入] 新增品牌 {added} 条（企业档案已同步，幂等）")


if __name__ == "__main__":
    main()
