"""统一数据库会话：全项目唯一 engine 出处（替代各 router 模块级 engine）。

测试通过 FastAPI dependency_overrides 替换 get_db，不再 monkeypatch 模块属性。
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
