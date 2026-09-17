"""Bing 搜索片段采集源（已验证可用）。

- 对标公司名的公开言论/口碑（知乎/牛客/脉脉/贴吧等）的搜索片段
- 多个查询模板，片段 + 标题做信号词打分，命中即记为一条 review 证据
- 只存标题 + 片段摘要 + URL，不存正文
"""

import asyncio
import re

import httpx

from normalize import normalize_company
from scoring.keywords import score_job_description
from sources.base import RawEvidence, Source

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")
# 通用模板 + 小红书站点限定模板（小红书内容经搜索引擎索引间接获取，
# 不直接抓取小红书：其接口有签名风控，员工笔记从搜索结果片段进入 review 权重 0.9）
QUERY_TEMPLATES = [
    "{kw} 双休吗",
    "{kw} 加班",
    "{kw} 大小周 单休",
    "{kw} 双休 site:xiaohongshu.com",
    "{kw} 加班 site:xiaohongshu.com",
]
_BLOCK_RE = re.compile(r"<li class=\"b_algo\".*?<h2[^>]*><a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a></h2>(.*?)</li>", re.S)
# 问句式标题（知乎「XX公司周末双休吗？」）本身含关键词但语义是疑问 →
# 仅用正文片段打分，避免把「想知道答案」误判为「确实双休」
QUESTION_WORDS = ("吗", "呢", "怎样", "如何", "怎么样", "？", "?")

# 百科/问答/泛新闻聚合 = 噪音源（易出现与员工待遇无关的 996/加班 字样）
DENYLIST_HOSTS = {
    "baike.baidu.com", "zhidao.baidu.com", "baike.sogou.com", "baike.so.com",
    "wenku.baidu.com", "wenku.so.com", "mp.weixin.qq.com",
    "news.qq.com", "www.toutiao.com", "www.sohu.com", "finance.sina.com.cn",
    "www.163.com", "news.163.com", "www.36kr.com", "baijiahao.baidu.com",
}
# 员工视角平台：权重高（职场口碑/问答/讨论）
EMPLOYEE_HOSTS = {
    "www.zhihu.com", "zhuanlan.zhihu.com", "www.nowcoder.com",
    "tieba.baidu.com", "maimai.cn", "www.maimai.cn",
    "www.xiaohongshu.com", "www.douban.com",
}


def parse_bing_results(html: str, keyword: str) -> list[RawEvidence]:
    """纯函数：Bing SERP HTML → 证据列表（可单测，不触网）。"""
    evs = []
    for m in _BLOCK_RE.finditer(html):
        href, title_html, body_html = m.groups()
        host = href.split("//")[-1].split("/")[0].lower()
        if host in DENYLIST_HOSTS or "bilibili.com" in host:
            continue
        title = re.sub(r"<[^>]+>", "", title_html)
        text = re.sub(r"<[^>]+>", "", body_html)
        text = re.sub(r"\s+", " ", text)
        if normalize_company(keyword) not in normalize_company(title + " " + text):
            continue
        is_question = any(q in title for q in QUESTION_WORDS)
        scored_text = text if is_question else title + " " + text
        if normalize_company(keyword) not in normalize_company(scored_text):
            continue
        score, kws = score_job_description(scored_text)
        if not kws:
            continue
        source_type = "review" if host in EMPLOYEE_HOSTS else "review_promo"
        evs.append(RawEvidence(
            company_key=keyword,
            company_raw=keyword,
            source_type=source_type,
            url=href,
            title=title.strip(),
            snippet=text.strip()[:160],
            keywords=kws,
            raw_score=score,
        ))
    return evs


class BingSnippetSource(Source):
    source_type = "review"

    def __init__(self, per_query_sleep: float = 3.0):
        self.sleep = per_query_sleep

    def _new_client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=20.0, follow_redirects=True,
        )

    async def fetch(self, keyword: str) -> list[RawEvidence]:
        evs: list[RawEvidence] = []
        client = self._new_client()
        try:
            for i, tpl in enumerate(QUERY_TEMPLATES):
                url = f"https://cn.bing.com/search?q={tpl.format(kw=keyword)}"
                resp = await asyncio.get_event_loop().run_in_executor(None, lambda: client.get(url))
                if resp.status_code != 200:
                    await asyncio.sleep(self.sleep)
                    continue
                evs += parse_bing_results(resp.text, keyword)
                await asyncio.sleep(self.sleep)
        finally:
            client.close()
        return evs