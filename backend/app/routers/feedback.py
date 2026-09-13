"""纠错反馈 API：数据纠错表单 → GitHub Issue（无感通道）。

- 不建新表：若涉及对象能匹配到企业，则复用 UgcReport（source_type='correction'）入审核队列
- 无论是否入队，都尝试将内容转为 GitHub Issue 发给维护者
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Company, UgcReport
from ..db.session import get_db
from ..services.github_feedback import create_issue
from .deps import check_rate_limit

router = APIRouter(prefix="/api")


@router.post("/feedback/correction")
async def submit_correction(payload: dict, request: Request, db: Session = Depends(get_db)):
    """数据纠错：{target, subject, detail}"""
    check_rate_limit(request.client.host if request.client else "unknown")

    subject = (payload.get("subject") or "").strip()
    detail = (payload.get("detail") or "").strip()
    if len(subject) < 2 or len(detail) < 5:
        from fastapi import HTTPException
        raise HTTPException(422, "subject 至少 2 字、detail 至少 5 字")

    # 若能匹配到企业，入本地审核队列（复用 UGC 表）
    company = db.scalars(select(Company).where(Company.name == subject)).first()
    if company:
        db.add(UgcReport(
            company_id=company.id,
            source_type="correction",
            description=detail,
            status="pending",
        ))
        db.commit()

    issue_url = await create_issue("correction", {
        "target": payload.get("target", "企业档案"),
        "subject": subject,
        "detail": detail,
    })
    return {
        "ok": True,
        "issue_url": issue_url,
        "message": "已提交到维护者 Issue" if issue_url else "已受理，维护者将人工核对（一般 48h）",
    }