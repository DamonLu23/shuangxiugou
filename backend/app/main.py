from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import validate_runtime_config
from .db.models import Brand
from .db.session import engine
from .routers import appeals, company, feedback, goods, jobs, search
from .services.brand import import_seed


@asynccontextmanager
async def lifespan(_: FastAPI):
    warnings = validate_runtime_config()
    for w in warnings:
        print(f"[配置警告] {w}")
    with Session(engine) as session:
        if session.query(Brand).count() == 0:
            n = import_seed(session)
            print(f"[启动] 已导入品牌映射 {n} 条")
    yield


app = FastAPI(title="双休购 API", version="0.2.0", lifespan=lifespan)
app.include_router(search.router)
app.include_router(company.router)
app.include_router(jobs.router)
app.include_router(goods.router)
app.include_router(appeals.router)
app.include_router(feedback.router)

# 隐私政策页（App Store 审核需要可访问 URL：https://域名/privacy.html 或直接挂本路径）
app.mount(
    "/privacy",
    StaticFiles(directory=str(Path(__file__).resolve().parents[2] / "data" / "privacy")),
    name="privacy",
)