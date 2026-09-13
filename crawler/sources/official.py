"""企业官网岗位源：抓取白名单（L1/L2）企业官网招聘页在招岗位。

策略：
- httpx 直抓 → 若判定为 SPA 壳（内容过小/无岗位关键词）→ Playwright 渲染兜底
- 通用解析：链接启发式（href 含 job/position/career 等 + 文本像岗位名）
- 支持每企业 CSS selector 覆盖（company_job_sources.csv 配置）
- 官网是「雇主实时在招列表」：每次全量采集 + 岗位表 active 老化 → 关闭岗位自动移除

配置：data/company_job_sources.csv
    company_name,careers_url,parser,enabled
    （parser: generic / selector:css选择器；enabled: true/false）
"""

import re
from urllib.parse import urljoin

import httpx

from sources.base import Source  # noqa: F401  （保持同目录导入风格一致）

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")

# 岗位链接特征词（href 命中其一即视为候选）
JOB_LINK_HINTS = ("job", "position", "zhiwei", "career", "recruit", "campus", "req")
# 排除链接（产品页/客服/FAQ/新闻等内容页常含 detail 等词）
JOB_HREF_EXCLUDE = ("/product", "/support", "/faq", "/news", "/shop", "/about",
                    "/service", "help", ".jpg", ".png", ".pdf")
# 导航/按钮类文本黑名单（避免把「登录」「查看更多」当岗位）
NAV_TEXT_BLOCKLIST = {
    "首页", "登录", "注册", "关于我们", "联系我们", "更多", "查看更多", "返回",
    "English", "搜索", "招聘首页", "社会招聘", "校园招聘", "实习生招聘",
    "职位搜索", "投递简历", "立即投递", "查看详情", "了解详情", "prev", "next",
}
_ANCHOR_RE = re.compile(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def filter_job_anchors(anchors: list[dict], base_url: str, max_items: int = 60) -> list[dict]:
    """纯函数：锚点列表 → 岗位候选（title/url）。

    anchors: [{title, href}]，供 httpx（正则抽取）与 Playwright（DOM 抽取）两条路复用。
    """
    jobs, seen = [], set()
    for a in anchors:
        title = _TAG_RE.sub("", a.get("title") or "")
        title = re.sub(r"\s+", " ", title).strip()
        href = (a.get("href") or "").strip()
        if not (2 <= len(title) <= 50) or not href:
            continue
        if title in NAV_TEXT_BLOCKLIST:
            continue
        if href.startswith(("javascript:", "#", "mailto:")):
            continue
        href_lower = href.lower()
        if any(x in href_lower for x in JOB_HREF_EXCLUDE):
            continue
        if not any(k in href_lower for k in JOB_LINK_HINTS):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        jobs.append({"title": title, "url": url})
        if len(jobs) >= max_items:
            break
    return jobs


def parse_official_jobs(html: str, base_url: str, max_items: int = 60) -> list[dict]:
    """纯函数：服务端渲染 HTML → 岗位候选。"""
    anchors = [{"href": m.group(1), "title": m.group(2)}
               for m in _ANCHOR_RE.finditer(html)]
    return filter_job_anchors(anchors, base_url, max_items)


def is_spa_shell(html: str) -> bool:
    """判断页面是否为 SPA 壳（内容过小或缺岗位关键词）。"""
    if len(html) < 3000:
        return True
    markers = ("职位", "岗位", "招聘", "job", "position")
    return not any(m in html for m in markers)


_DOM_ANCHORS_JS = """() => {
    const out = [];
    document.querySelectorAll('a[href]').forEach(a => {
        out.push({ title: (a.textContent || '').trim().slice(0, 120), href: a.getAttribute('href') || '' });
    });
    return out;
}"""

_QUERY_SELECTOR_JS = """(sel) => {
    const out = [];
    document.querySelectorAll(sel).forEach(a => {
        out.push({ title: (a.textContent || '').trim().slice(0, 120), href: a.getAttribute('href') || a.dataset.url || '' });
    });
    return out;
}"""


class OfficialJobsSource:
    """官网岗位采集（每企业一条配置）。"""

    source_type = "official"
    settle_ms = 6000

    def __init__(self, browser=None):
        self._browser = browser

    def use_browser(self, browser):
        self._browser = browser

    async def fetch_company(self, company_name: str, careers_url: str,
                            parser: str = "generic") -> list[dict]:
        """抓取单企业官网招聘页，返回 [{title, url}]。"""
        html = await self._get_html(careers_url)
        anchors = None
        if html is not None and not is_spa_shell(html):
            return parse_official_jobs(html, careers_url)

        # SPA 壳或抓取失败 → Playwright 渲染
        anchors = await self._render_anchors(careers_url, parser)
        if anchors is None:
            return []
        return filter_job_anchors(anchors, careers_url)

    async def _get_html(self, url: str):
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": UA}, timeout=15, follow_redirects=True
            ) as client:
                resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
        except httpx.HTTPError:
            pass
        return None

    async def _render_anchors(self, url: str, parser: str):
        if self._browser is None:
            return None
        page = None
        try:
            ctx = await self._browser.new_context(user_agent=UA, locale="zh-CN",
                                                  viewport={"width": 1280, "height": 900})
            page = await ctx.new_page()
            await page.goto(url, timeout=40000, wait_until="domcontentloaded")
            await page.wait_for_timeout(self.settle_ms)
            if parser.startswith("selector:"):
                sel = parser.split(":", 1)[1]
                return await page.evaluate(_QUERY_SELECTOR_JS, sel)
            return await page.evaluate(_DOM_ANCHORS_JS)
        except Exception as e:
            print(f"    [官网渲染失败] {url}: {type(e).__name__} {str(e)[:80]}")
            return None
        finally:
            if page:
                ctx = page.context
                await page.close()
                await ctx.close()