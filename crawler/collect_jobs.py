"""岗位采集：收集白名单企业（L1/L2）的在招岗位入库。

数据源（sources_config.json 控制启用）：
- zhaopin：智联公司主页岗位列表（品牌 key 检索）
- official：企业官网招聘页（data/company_job_sources.csv 逐家配置，SPA 可渲染）

老化机制：本轮**成功采集**的来源，对每家企业未再采集到的岗位置 active=False
（采集失败的来源不动），本次采集到的 URL 置 active=True → 岗位关闭/下架自动移除，
且单次运行失败不会误删岗位。

用法:
    .venv/bin/python -u collect_jobs.py --limit 5     # 只跑前 5 家（验证用）
    .venv/bin/python -u collect_jobs.py                # 全量白名单
    .venv/bin/python -u collect_jobs.py --dry-run      # 只采集不写库
"""

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.models import Base, Brand, Company, Job, WHITELIST_LEVELS
from app.db.session import engine
from health import new_health, record, write_report
from sources.registry import load_config, make_job_sources


def whitelist_companies(limit: int = 0) -> list[tuple[Company, str]]:
    """白名单企业 + 其智联检索用品牌 key（如 三星、顺丰）。"""
    out = []
    with Session(engine) as db:
        stmt = (
            select(Company, Brand.name)
            .join(Brand, Brand.company_id == Company.id)
            .where(Company.level.in_(WHITELIST_LEVELS))
            .order_by(Company.level, Company.name)
        )
        for c, brand_key in db.execute(stmt).all():
            out.append((c, brand_key))
    return out[:limit] if limit else out


@asynccontextmanager
async def _browser_ctx(owner):
    """有需要浏览器的源时复用一个浏览器实例。"""
    if owner is None:
        yield None
    else:
        async with owner.launch_shared() as browser:
            yield browser


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--politeness", type=float, default=1.5)
    args = ap.parse_args()

    companies = whitelist_companies(args.limit)
    cfg = load_config()
    print(f"[岗位采集] 白名单企业 {len(companies)} 家")

    Base.metadata.create_all(engine)
    source_names = [name for name, _, _ in make_job_sources(cfg)]
    already = set()
    with Session(engine) as db:
        if not args.dry_run:
            already = {u for u in db.scalars(select(Job.url)).all()}
            db.commit()

    health = new_health()
    total = 0
    sources = make_job_sources(cfg)
    browser_owner = next((s for _, s, _ in sources if hasattr(s, "launch_shared")), None)

    async with _browser_ctx(browser_owner) as browser:
        for _, src, opts in sources:
            if hasattr(src, "use_browser") and browser is not None:
                src.use_browser(browser)
        for i, (c, brand_key) in enumerate(companies, 1):
            company_jobs: list[dict] = []
            source_ok: set = set()  # 本轮成功采集的来源（只对这些来源老化）
            for name, src, opts in sources:
                try:
                    if name == "zhaopin":
                        got = await src.collect_jobs(brand_key)
                    elif name == "official":
                        if not any(r["company_name"] == c.name
                                   for r in opts.get("companies", [])):
                            continue  # 该企业未配置官网源：不采集也不老化
                        got = await _collect_official(src, opts, c.name)
                    else:
                        continue
                    source_ok.add(name)
                    company_jobs += got
                    record(health, name, ok=True, items=len(got))
                except Exception as e:
                    record(health, name, ok=False)
                    print(f"  [{name} 失败] {c.name}: {type(e).__name__} {str(e)[:80]}")

            if args.dry_run:
                print(f"  [{i}/{len(companies)}] {c.name}: {len(company_jobs)} 个岗位（dry-run）")
                total += len(company_jobs)
                continue

            added = _save_jobs(c, brand_key, company_jobs, already, source_ok)
            total += added
            print(f"  [{i}/{len(companies)}] {c.name}: 采集 {len(company_jobs)}，新增 {added}")
            if i < len(companies):
                await asyncio.sleep(args.politeness)

    health_md = Path(__file__).resolve().parents[1] / "data" / "source_health_jobs.md"
    write_report(health, health_md)

    with Session(engine) as db:
        active = db.query(Job).filter(Job.active.is_(True),
                                      Job.source.in_(source_names)).count()
        pending_ugc = db.query(Job).filter(Job.active.is_(False),
                                           Job.source == "ugc").count()
    print(f"[岗位采集] 完成：本次新增 {total}，在招活跃 {active}，UGC 待审 {pending_ugc}")
    print(f"[岗位采集] 源健康报告: {health_md}")
    print("下一步: backend 导出 .venv/bin/python scripts/export_data.py")


async def _collect_official(src, opts, company_name: str) -> list[dict]:
    """官网源：仅采集该企业在配置表且 enabled 的条目。"""
    for cfg_row in opts.get("companies", []):
        if cfg_row["company_name"] == company_name:
            jobs = await src.fetch_company(company_name,
                                           cfg_row["careers_url"],
                                           cfg_row.get("parser", "generic"))
            return [{"title": j["title"], "url": j["url"], "city": "",
                     "welfare": [], "salary": "", "source": "official"}
                    for j in jobs]
    return []


def _save_jobs(company: Company, brand_key: str, jobs: list[dict], already: set,
               age_sources: set = None) -> int:
    """岗位入库：URL 去重 + active 置活 + 按公司/来源老化。返回新增数。

    age_sources 只包含本轮**成功采集**的来源：采集失败的来源不老化，
    避免一次运行失败就把该企业岗位全部标记为关闭（旧实现全局预老化）。
    """
    added = 0
    age_sources = age_sources or set()
    with Session(engine) as db:
        collected_urls = {j["url"] for j in jobs}
        for src in age_sources:
            for old in db.scalars(select(Job).where(
                    Job.company_id == company.id, Job.source == src)):
                if old.url not in collected_urls:
                    old.active = False  # 雇主已下架（官网）或平台不再展示
        for j in jobs:
            src = j.get("source", "zhaopin")
            if j["url"] in already:
                old = db.scalars(select(Job).where(Job.url == j["url"])).first()
                if old:
                    old.active = True
                continue
            company_row = db.get(Company, company.id)
            db.add(Job(
                title=j["title"],
                company_id=company.id,
                company_name=company_row.name if company_row else j.get("company_raw", brand_key),
                city=j.get("city", ""),
                tags=",".join(j.get("welfare", [])),
                salary=j.get("salary", ""),
                url=j["url"],
                source=src,
                collected_at=date.today(),
                active=True,
            ))
            already.add(j["url"])
            added += 1
        db.commit()
    return added


if __name__ == "__main__":
    asyncio.run(main())