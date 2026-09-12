"""求职 API：白名单岗位搜索 + UGC 岗位上报/审核。

白名单承诺：所有岗位仅来自 L1/L2 企业，其他企业岗位一律不展示。
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Company, Job, LEVEL_NAMES
from ..db.session import get_db
from .deps import check_rate_limit, require_admin

router = APIRouter(prefix="/api")

WHITELIST_LEVELS = (1, 2)


@router.get("/jobs/search")
async def jobs_search(
    q: str = Query(..., min_length=1, description="岗位关键词，如 前端/运营/会计"),
    city: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """搜索白名单企业（L1/L2）的在招岗位。"""
    base = (
        select(Job.id)
        .join(Company, Company.id == Job.company_id)
        .where(Job.active.is_(True), Company.level.in_(WHITELIST_LEVELS),
               Job.title.contains(q))
    )
    if city:
        base = base.where(Job.city == city)

    stmt = (
        select(Job, Company.level, Company.confidence)
        .join(Company, Company.id == Job.company_id)
        .where(Job.active.is_(True), Company.level.in_(WHITELIST_LEVELS),
               Job.title.contains(q))
        .order_by(Company.level, Company.confidence.desc(), Job.collected_at.desc())
    )
    if city:
        stmt = stmt.where(Job.city == city)

    total = len(db.execute(base).all())
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "query": q,
        "city": city,
        "total": total,
        "page": page,
        "jobs": [{
            "id": j.id,
            "title": j.title,
            "company_id": j.company_id,
            "company_name": j.company_name,
            "company_level": lv,
            "company_level_name": LEVEL_NAMES.get(lv),
            "confidence": round(conf, 3),
            "city": j.city,
            "salary": j.salary,
            "tags": (j.tags or "").split(","),
            "url": j.url,
            "collected_at": str(j.collected_at),
        } for j, lv, conf in rows],
    }


@router.post("/jobs/report")
async def jobs_report(payload: dict, request: Request, db: Session = Depends(get_db)):
    """UGC 岗位上报：用户提交见过的双休企业岗位（审核后收录）。"""
    check_rate_limit(request.client.host if request.client else "unknown")
    title = (payload.get("title") or "").strip()
    company_name = (payload.get("company_name") or "").strip()
    if len(title) < 2 or len(company_name) < 2:
        raise HTTPException(422, "title 与 company_name 至少 2 字")

    company = db.scalars(select(Company).where(Company.name == company_name)).first()
    job = Job(
        title=title,
        company_id=company.id if company else None,
        company_name=company_name,
        city=payload.get("city"),
        tags=",".join(payload.get("tags") or []),
        salary=payload.get("salary", ""),
        url=payload.get("url", "") or "ugc://job",
        source="ugc",
        collected_at=date.today(),
        active=False,  # 待审核；且仅白名单企业岗位最终可见
    )
    db.add(job)
    db.commit()
    return {"ok": True, "job_id": job.id, "status": "pending",
            "message": "已提交，审核通过且企业为白名单后展示"}


@router.get("/admin/jobs")
async def admin_jobs(
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """岗位审核队列：source=ugc 的待审岗位。"""
    rows = db.scalars(
        select(Job).where(Job.source == "ugc", Job.active.is_(False))
        .order_by(Job.collected_at.desc())
    ).all()
    return [{
        "job_id": j.id,
        "title": j.title,
        "company_name": j.company_name,
        "city": j.city,
        "salary": j.salary,
        "url": j.url,
        "collected_at": str(j.collected_at),
    } for j in rows]


@router.post("/admin/jobs/{job_id}/review")
async def admin_jobs_review(
    job_id: int,
    payload: dict,
    _: bool = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """岗位审核：approve（激活）/ reject（删除）。企业非白名单时 approve 挂起。"""
    action = payload.get("action")
    if action not in ("approve", "reject"):
        raise HTTPException(422, "action 需为 approve 或 reject")
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")
    if action == "reject":
        db.delete(job)
        db.commit()
        return {"ok": True, "job_id": job_id, "status": "rejected"}

    company = db.get(Company, job.company_id) if job.company_id else None
    if not company or company.level not in WHITELIST_LEVELS:
        job.active = False
        db.commit()
        return {"ok": False, "job_id": job_id, "status": "held",
                "message": "企业不在白名单（L1/L2），岗位暂不展示；建议先完善企业档案"}
    job.active = True
    db.commit()
    return {"ok": True, "job_id": job_id, "status": "approved"}