"""电商商品候选源（苏宁易购，httpx 静态页）：只抓商品信息，**不存电商链接**。

背景（2026-09 实测）：
- 京东搜索已改为登录墙 + React SPA：headless/有头均 302 到 passport.jd.com，
  渲染后无商品节点 → 原定的京东 Playwright 方案不可用（记录于 docs/sources.md）；
- 苏宁易购搜索页为服务端渲染静态 HTML，httpx 可直取（低频 + 限速使用）。

产物只含 标题/SKU/品类猜测（data/goods_candidates.csv），
商品链接一律由人工补官网/官方旗舰店（用户定调：只抓信息，不放链接）。
"""

import re

import httpx

SUNING_SEARCH_URL = "https://search.suning.com/{kw}/"

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/148.0 Safari/537.36")
_TAG_RE = re.compile(r"<[^>]+>")
_EM_RE = re.compile(r"<em[^>]*>.*?</em>", re.S)  # 隐藏卖点文案（display:none）
# 商品名区块 → 商品链接（链接仅用于提取 SKU，不落盘）
_PRODUCT_RE = re.compile(
    r'class="title-selling-point".*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_SKU_RE = re.compile(r"/(\d+)\.html")

# 配件/周边噪音（好物目录要的是代表商品，不是壳膜线）
ACCESSORY_WORDS = (
    "手机壳", "保护壳", "保护套", "钢化膜", "贴膜", "镜头膜", "数据线", "充电线",
    "充电器", "充电头", "支架", "贴纸", "挂绳", "收纳包", "鼠标垫", "键帽",
    "替换头", "滤芯", "配件", "二手", "翻新",
)

# 标题关键词 → 品类（供人工确认时参考；未知留空）
CATEGORY_HINTS = {
    "电饭煲": "厨房家电", "电压力锅": "厨房家电", "破壁机": "厨房家电",
    "空气炸锅": "厨房家电", "电水壶": "厨房家电", "豆浆机": "厨房家电",
    "冰箱": "家电", "洗衣机": "家电", "空调": "家电", "电视": "家电",
    "热水器": "家电", "吸尘器": "家电", "扫地机器人": "家电",
    "手机": "数码", "笔记本": "数码", "平板": "数码", "耳机": "数码",
    "键盘": "数码", "鼠标": "数码", "显示器": "数码", "路由器": "数码",
    "牛奶": "食品饮料", "咖啡": "食品饮料", "茶": "食品饮料", "矿泉水": "食品饮料",
    "零食": "食品饮料", "坚果": "食品饮料", "酱油": "食品饮料", "食用油": "食品饮料",
    "运动鞋": "运动", "跑鞋": "运动", "球鞋": "运动", "羽绒服": "服饰",
    "T恤": "服饰", "衬衫": "服饰", "床垫": "家居", "枕头": "家居",
    "洗发水": "日化", "牙膏": "日化", "洗衣液": "日化", "纸巾": "日化",
}


def clean_title(raw: str, max_len: int = 80) -> str:
    """清洗商品标题：去隐藏卖点、去【】促销词、去标签、折叠空白、截断。"""
    title = _EM_RE.sub("", raw or "")
    title = _TAG_RE.sub("", title)
    title = re.sub(r"【[^】]*】", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:max_len].strip()


def is_accessory(title: str) -> bool:
    return any(w in title for w in ACCESSORY_WORDS)


def guess_category(title: str) -> str:
    for word, cat in CATEGORY_HINTS.items():
        if word in title:
            return cat
    return ""


def filter_candidates(items: list[dict], brand_key: str, max_items: int = 10) -> list[dict]:
    """纯函数：原始商品列表 → 品牌候选（匹配品牌/去配件/去重/清洗）。"""
    brand_norm = brand_key.replace(" ", "").upper()
    out, seen = [], set()
    for it in items:
        title = clean_title(it.get("title", ""))
        if not title or len(title) < 4:
            continue
        if brand_norm not in title.replace(" ", "").upper():
            continue
        if is_accessory(title):
            continue
        sku = it.get("sku") or title
        if sku in seen:
            continue
        seen.add(sku)
        out.append({
            "sku": sku,
            "product": title,
            "shop": (it.get("shop") or "").strip(),
            "category": guess_category(title),
        })
        if len(out) >= max_items:
            break
    return out


def parse_suning_results(html: str, brand_key: str, max_items: int = 10) -> list[dict]:
    """纯函数：苏宁搜索页 HTML → 品牌商品候选（可单测，不触网）。"""
    items = []
    for href, inner in _PRODUCT_RE.findall(html):
        m = _SKU_RE.search(href)
        items.append({
            "sku": m.group(1) if m else "",
            "title": inner,
            "shop": "",
        })
    return filter_candidates(items, brand_key, max_items)


class SuningGoodsSource:
    """苏宁商品候选采集（每品牌一次搜索，httpx + 限速）。"""

    source_type = "suning_goods"

    def fetch_candidates(self, brand_key: str, max_items: int = 10) -> list[dict]:
        url = SUNING_SEARCH_URL.format(kw=brand_key)
        try:
            with httpx.Client(headers={"User-Agent": _UA},
                              timeout=20.0, follow_redirects=True) as client:
                resp = client.get(url)
            if resp.status_code != 200:
                print(f"    [苏宁搜索失败] {brand_key}: HTTP {resp.status_code}")
                return []
            return parse_suning_results(resp.text, brand_key, max_items)
        except httpx.HTTPError as e:
            print(f"    [苏宁搜索失败] {brand_key}: {type(e).__name__} {str(e)[:80]}")
            return []
