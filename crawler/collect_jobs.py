"""M1 岗位采集：收集白名单企业（L1/L2）的在招岗位入库。

用法:
    .venv/bin/python -u collect_jobs.py --limit 5     # 只跑前 5 家（验证用）
    .venv/bin/python -u collect_jobs.py                # 全量白名单
    .venv/bin/python -u collect_jobs.py --dry-run --limit 2   # 只采集不写库

数据来源：智联公司主页岗位列表（与证据采集同链路，仅转存岗位实体）。
每次运行先标记旧 zhaopin 岗位 active=False，本次采集到的置 active=True（自然老化）。
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Base, Brand, Company, Job
from app.db.session import engine
from sources.zhaopin import ZhaopinSource


def whitelist_companies(limit: int = 0) -> list[tuple[Company, str]]:
    """白名单企业 + 其智联检索用品牌 key（如 三星、顺丰）。"""
    out = []
    with Session(engine) as db:
        stmt = (
            select(Company, Brand.name)
            .join(Brand, Brand.company_id == Company.id)
            .where(Company.level.in_((1, 2)))
            .order_by(Company.level, Company.name)
        )
        for c, brand_key in db.execute(stmt).all():
            out.append((c, brand_key))
    return out[:limit] if limit else out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--politeness", type=float, default=1.5)
    args = ap.parse_args()

    companies = whitelist_companies(args.limit)
    print(f"[岗位采集] 白名单企业 {len(companies)} 家")

    Base.metadata.create_all(engine)
    already = set()
    with Session(engine) as db:
        if not args.dry_run:
            for j in db.scalars(select(Job).where(Job.source == "zhaopin")):
                j.active = False
            already = {u for u in db.scalars(select(Job.url)).all()}
            db.commit()

    zhaopin = ZhaopinSource(city_id="530")
    total = 0
    async with zhaopin.launch_shared():
        for i, (c, brand_key) in enumerate(companies, 1):
            try:
                jobs = await zhaopin.collect_jobs(brand_key)
            except Exception as e:
                print(f"  [{i}/{len(companies)}] {c.name}: 失败 {type(e).__name__} {str(e)[:80]}")
                continue
            if args.dry_run:
                print(f"  [{i}/{len(companies)}] {c.name}: {len(jobs)} 个岗位（dry-run）")
                total += len(jobs)
                continue
            with Session(engine) as db:
                for j in jobs:
                    if j["url"] in already:
                        old = db.scalars(select(Job).where(Job.url == j["url"])).first()
                        if old:
                            old.active = True
                        continue
                    company_row = db.get(Company, c.id)
                    db.add(Job(
                        title=j["title"],
                        company_id=c.id,
                        company_name=company_row.name if company_row else j["company_raw"],
                        city=j["city"],
                        tags=",".join(j["welfare"]),
                        salary=j["salary"],
                        url=j["url"],
                        source="zhaopin",
                        collected_at=date.today(),
                        active=True,
                    ))
                    already.add(j["url"])
                    total += 1
                db.commit()
            print(f"  [{i}/{len(companies)}] {c.name}: 新收录 {len(jobs)} 个岗位")
            if i < len(companies):
                await asyncio.sleep(args.politeness)

    with Session(engine) as db:
        active = db.query(Job).filter(Job.active.is_(True), Job.source == "zhaopin").count()
        pending_ugc = db.query(Job).filter(Job.active.is_(False), Job.source == "ugc").count()
    print(f"[岗位采集] 完成：本次新增 {total}，在招活跃 {active}，UGC 待审 {pending_ugc}")
    print("下一步: backend 导出 .venv/bin/python scripts/export_data.py")


if __name__ == "__main__":
    asyncio.run(main())