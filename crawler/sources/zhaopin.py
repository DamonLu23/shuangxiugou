"""智联招聘采集源（两条链路，均已实测可用）。

链路 A（搜索页）: sou.zhaopin.com/?kw=公司名 → job-card 卡片 → 匹配公司的 companydetail 链接
链路 B（公司主页）: companydetail/jobs-CZxxx.htm → .job-onlinelist__jobs__item 岗位块
                    → 标题 + 福利标签（做五休二/三班倒 等） → 信号词打分

性能（REVIEW P1）：支持跨公司复用同一浏览器实例（use_browser + launch_shared），
避免 202 家 = 202 次 chromium 启动；导航失败自动重试一次。
"""

import re
from contextlib import asynccontextmanager
from typing import List, Optional

from playwright.async_api import Browser, async_playwright

from normalize import match_key
from scoring.keywords import score_job_description
from sources.base import RawEvidence, Source

_SEARCH_CARDS_JS = """() => {
    const out = [];
    document.querySelectorAll('.job-card').forEach(el => {
        const c = el.querySelector('.job-card__company-name');
        const t = el.querySelector('.vue-clamp__text') || el.querySelector('[aria-label]');
        if (!c || !t) return;
        out.push({ company: c.textContent.trim(), href: c.href, title: (t.getAttribute('aria-label') || t.textContent).trim() });
    });
    return out;
}"""

_JOBS_ITEMS_JS = """() => {
    const out = [];
    document.querySelectorAll('.job-onlinelist__jobs__item').forEach(el => {
        const a = el.querySelector('.job-onlinelist__jobs__info__href');
        const welfare = Array.from(el.querySelectorAll('.job-onlinelist__jobs__welfare__txt')).map(x => x.textContent.trim());
        if (!a) return;
        out.push({ title: a.textContent.trim(), href: a.href, welfare });
    });
    return out;
}"""

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")


class ZhaopinSource(Source):
    source_type = "job_post"
    settle_ms = 6000
    max_company_pages = 3
    nav_timeout_ms = 40000

    def __init__(self, city_id: str = "", seen_company_uids: Optional[set] = None):
        self.city_id = city_id
        self.seen = seen_company_uids if seen_company_uids is not None else set()
        self._browser: Optional[Browser] = None

    # ---- 浏览器生命周期 ----
    def use_browser(self, browser: Browser):
        """绑定外部浏览器实例（跨公司复用，避免反复启动 chromium）。"""
        self._browser = browser

    @asynccontextmanager
    async def launch_shared(self):
        """共享浏览器上下文：async with src.launch_shared() as browser: ..."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chromium", headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                self.use_browser(browser)
                yield browser
            finally:
                self._browser = None
                await browser.close()

    async def _new_page(self):
        ctx = await self._browser.new_context(
            user_agent=_UA, locale="zh-CN",
            viewport={"width": 1280, "height": 900})
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return await ctx.new_page()

    async def _goto(self, page, url: str):
        """导航 + 失败重试一次（智联偶发超时）。"""
        try:
            await page.goto(url, timeout=self.nav_timeout_ms, wait_until="domcontentloaded")
        except Exception:
            await page.wait_for_timeout(2000)
            await page.goto(url, timeout=self.nav_timeout_ms, wait_until="domcontentloaded")
        await page.wait_for_timeout(self.settle_ms)

    # ---- 采集 ----
    async def fetch(self, keyword: str) -> list[RawEvidence]:
        evs: list[RawEvidence] = []
        if self._browser is not None:
            return await self._fetch_with(keyword)
        # 未绑定共享浏览器：单次独立启动（兼容单公司调用/测试）
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                channel="chromium", headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                self._browser = browser
                evs = await self._fetch_with(keyword)
            finally:
                self._browser = None
                await browser.close()
        return evs

    async def _fetch_with(self, keyword: str) -> list[RawEvidence]:
        page = await self._new_page()
        try:
            companies = await self._collect_matched_companies(page, keyword)
            evs: list[RawEvidence] = []
            for company in companies[: self.max_company_pages]:
                evs += await self._collect_jobs(page, keyword, company)
            return evs
        finally:
            ctx = page.context
            await page.close()
            await ctx.close()

    async def _collect_matched_companies(self, page, keyword) -> List[dict]:
        url = f"https://sou.zhaopin.com/?kw={keyword}"
        if self.city_id:
            url += f"&cityId={self.city_id}"
        try:
            await self._goto(page, url)
            cards = await page.evaluate(_SEARCH_CARDS_JS)
        except Exception as e:
            print(f"    [智联搜索失败] {keyword}: {type(e).__name__} {str(e)[:80]}")
            return []

        matched = {}
        for c in cards:
            if not match_key(c["company"], keyword):
                continue
            m = re.search(r"companydetail/(CZ[A-Z0-9]+)\.htm", c["href"])
            if not m:
                continue
            uid = m.group(1)
            if uid in self.seen:
                continue
            self.seen.add(uid)
            matched[uid] = {
                "name": c["company"],
                "url": f"https://www.zhaopin.com/companydetail/jobs-{uid}.htm",
            }
        return list(matched.values())

    async def _collect_jobs(self, page, keyword, company) -> list[RawEvidence]:
        try:
            await self._goto(page, company["url"])
            items = await page.evaluate(_JOBS_ITEMS_JS)
        except Exception as e:
            print(f"    [智联公司页失败] {keyword}/{company['name']}: {type(e).__name__} {str(e)[:80]}")
            return []

        evs = []
        for it in items:
            raw = f"{it['title']} {' '.join(it['welfare'])}"
            score, kws = score_job_description(raw)
            if not kws:
                continue
            evs.append(RawEvidence(
                company_key=keyword,
                company_raw=company["name"],
                source_type=self.source_type,
                url=it["href"] or company["url"],
                title=it["title"],
                snippet=", ".join(it["welfare"])[:160],
                keywords=kws,
                raw_score=score,
            ))
        return evs