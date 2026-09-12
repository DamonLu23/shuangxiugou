"""企业申诉 API：白名单更正/删除请求（APPEAL.md 的 48h 承诺落地）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Appeal, Company
from ..db.session import get_db
from .deps import require_admin

router = APIRouter(prefix="/api")


@router.post("/companies/{company_id}/appeal")
async def create_appeal(company_id: int, payload: dict, db: Session = Depends(get_db)):
    """企业申诉：提交更正/删除请求。"""
    reason = (payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise HTTPException(422, "reason 至少 5 字（说明为何需要更正/删除）")
    if not db.get(Company, company_id):
        raise HTTPException(404, "企业不存在")

    appeal = Appeal(
        company_id=company_id,
        contact=(payload.get("contact") or "").strip()[:128],
        reason=reason,
        evidence_url=payload.get("evidence_url", ""),
        status="open",
    )
    db.add(appeal)
    db.commit()
    return {"ok": True, "appeal_id": appeal.id, "status": "open",
            "message": "已受理，一般 48 小时内处理（见仓库 APPEAL.md）"}


@router.get("/admin/appeals")
async def admin_appeals(
    status: str = "open",
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Appeal, Company.name)
        .join(Company, Company.id == Appeal.company_id)
        .where(Appeal.status == status)
        .order_by(Appeal.created_at.desc())
    )
    return [{
        "appeal_id": a.id,
        "company_id": a.company_id,
        "company_name": name,
        "contact": a.contact,
        "reason": a.reason,
        "evidence_url": a.evidence_url,
        "created_at": a.created_at.isoformat(),
    } for a, name in db.execute(stmt).all()]


@router.post("/admin/appeals/{appeal_id}/resolve")
async def resolve_appeal(
    appeal_id: int,
    payload: dict,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """处理申诉：resolve（已处理）/ reject（驳回申诉）。"""
    action = payload.get("action")
    if action not in ("resolve", "reject"):
        raise HTTPException(422, "action 需为 resolve 或 reject")
    appeal = db.get(Appeal, appeal_id)
    if not appeal:
        raise HTTPException(404, "申诉不存在")
    appeal.status = "resolved" if action == "resolve" else "rejected"
    appeal.handler_note = payload.get("note", "")
    appeal.handled_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "appeal_id": appeal_id, "status": appeal.status}