import time
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import Company, Evidence, LEVEL_NAMES, UgcReport, WHITELIST_LEVELS
from ..db.session import get_db
from ..services.levels import recalc_company, weight_for
from ..services.signalkeys import score_job_description
from .deps import check_rate_limit, require_admin

router = APIRouter(prefix="/api")

# UGC 证据来源校验集合（纠错类走 /api/feedback/correction，不经此入口）
UGC_SOURCE_TYPES = {"ugc_offer", "ugc_contract", "ugc_other"}


@router.get("/companies")
async def company_list(
    level: Optional[int] = Query(None, ge=1, le=2, description="白名单内筛选：1 或 2"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """企业档案列表（白名单承诺：只返回 L1/L2 企业）。"""
    stmt = (select(Company.id, Company.name, Company.level, Company.confidence, Company.disputed)
            .where(Company.level.in_(WHITELIST_LEVELS)))
    if level:
        stmt = stmt.where(Company.level == level)
    stmt = stmt.order_by(Company.level, Company.confidence.desc()).limit(limit)
    rows = db.execute(stmt).all()
    return [{
        "id": r.id, "name": r.name, "level": r.level,
        "level_name": LEVEL_NAMES.get(r.level, "待验证"),
        "confidence": round(r.confidence, 3),
        "disputed": bool(r.disputed),
    } for r in rows]


@router.get("/companies/{company_id}")
async def company_detail(company_id: int, db: Session = Depends(get_db)):
    """企业双休档案（白名单承诺：仅 L1/L2 企业可访问，其余 404）。"""
    c = db.get(Company, company_id)
    if not c or c.level not in WHITELIST_LEVELS:
        raise HTTPException(404, "企业不存在或未收录")
    evs = db.execute(
        select(Evidence).where(Evidence.company_id == company_id)
        .order_by(Evidence.raw_score.desc())
    ).scalars().all()
    return {
        "id": c.id,
        "name": c.name,
        "level": c.level,
        "level_name": LEVEL_NAMES.get(c.level, "待验证"),
        "confidence": round(c.confidence, 3),
        "disputed": bool(c.disputed),
        "evidence_count": len(evs),
        "evidences": [{
            "source_type": e.source_type,
            "url": e.url,
            "title": "",
            "keywords": (e.keywords or "").split(","),
            "raw_score": e.raw_score,
            "collected_at": str(e.collected_at),
        } for e in evs[:20]],
    }


@router.post("/companies/{company_id}/report")
async def report_company(
    company_id: int,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    """UGC 上报：用户提交工时描述/截图，进入待审核队列（不直接生效）。

    payload: {"source_type": "ugc_contract|ugc_offer|ugc_other",
              "description": "合同约定做五休二，实际周末双休...",
              "image_url": "https://...（可选）"}
    """
    check_rate_limit(request.client.host if request.client else "unknown")

    if payload.get("source_type") not in UGC_SOURCE_TYPES:
        raise HTTPException(422, f"source_type 需为 {sorted(UGC_SOURCE_TYPES)}")
    desc = (payload.get("description") or "").strip()
    if len(desc) < 5:
        raise HTTPException(422, "description 至少 5 字（描述你的实际工时安排）")

    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "企业不存在")
    report = UgcReport(
        company_id=company_id,
        source_type=payload["source_type"],
        description=desc,
        image_url=payload.get("image_url"),
        status="pending",
    )
    db.add(report)
    db.commit()
    return {
        "ok": True,
        "report_id": report.id,
        "status": "pending",
        "message": "已受理，人工审核后生效（一般 1~3 个工作日）",
    }


@router.get("/admin/reports")
async def admin_reports(
    status: str = Query("pending"),
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核队列列表。status: pending / approved / rejected。"""
    stmt = (
        select(
            UgcReport.id.label("rid"),
            UgcReport.company_id,
            UgcReport.source_type,
            UgcReport.description,
            UgcReport.image_url,
            UgcReport.status,
            UgcReport.created_at,
            Company.name.label("company_name"),
        )
        .join(Company, Company.id == UgcReport.company_id)
        .where(UgcReport.status == status)
        .order_by(UgcReport.created_at.desc())
    )
    rows = db.execute(stmt).all()
    return [{
        "report_id": r.rid,
        "company_id": r.company_id,
        "company_name": r.company_name,
        "source_type": r.source_type,
        "description": r.description,
        "image_url": r.image_url,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
    } for r in rows]


@router.post("/admin/reports/{report_id}/review")
async def admin_review(
    report_id: int,
    payload: dict,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """审核：action=approve 通过（转证据+重算企业等级）/ reject 驳回。"""
    action = payload.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(422, "action 需为 approve 或 reject")

    report = db.get(UgcReport, report_id)
    if not report:
        raise HTTPException(404, "上报不存在")
    if report.status != "pending":
        raise HTTPException(409, f"该上报已处理（{report.status}）")

    if action == "reject":
        report.status = "rejected"
        report.reviewer_note = payload.get("note", "")
        report.reviewed_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "report_id": report_id, "status": "rejected"}

    # 通过：转正为 Evidence（权重入库快照），随后重算企业等级
    raw_score, kws = score_job_description(report.description)
    company = db.get(Company, report.company_id)
    evidence = Evidence(
        company_id=report.company_id,
        source_type=report.source_type,
        url=report.image_url or f"ugc://report/{report.id}",
        keywords=",".join(kws) or "人工标记",
        raw_score=raw_score if kws else 0.0,
        weight=weight_for(report.source_type),
        collected_at=date.today(),
        reviewed=True,
    )
    db.add(evidence)
    report.status = "approved"
    report.reviewer_note = payload.get("note", "")
    report.reviewed_at = datetime.utcnow()

    if company:
        recalc_company(company, db)
        db.commit()
        db.refresh(company)
        return {
            "ok": True,
            "report_id": report_id,
            "status": "approved",
            "evidence_id": evidence.id,
            "raw_score": raw_score,
            "keywords": kws,
            "company_level": company.level,
            "company_confidence": round(company.confidence, 3),
        }
    db.commit()
    return {"ok": True, "report_id": report_id, "status": "approved"}