"""公司名归一化与种子匹配。

规则：
1. 去掉 分公司/子公司/括号城市 等后缀细节
2. 与种子表主键匹配：归一化名以 主键 开头，且剩余部分是常见公司后缀词
3. 不匹配则丢弃该证据（避免「新疆华为商贸」错挂到华为）
"""

import re

_SUFFIX_DETAIL = [
    "分公司", "子公司", "研究所", "研究院", "办事处", "营业部", "门店", "分店",
    "金融事业部", "科技园", "产业园",
]
_CORP_BODIES = [
    "集团", "有限公司", "股份有限公司", "公司",
    "技术", "科技", "信息", "电子", "数码", "网络", "软件", "智能", "汽车", "通信",
    "生物", "食品", "饮料", "乳业", "服饰", "体育", "珠宝", "日化", "家电", "控股",
    "发展", "贸易", "文化", "传媒", "互娱", "健康", "医疗", "物流", "生活", "在线",
    "零售", "出行", "消费", "工业", "能源", "新能源", "航空",
]

_SUFFIX_DETAIL_RE = "|".join(_SUFFIX_DETAIL)
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")


def normalize_company(raw: str) -> str:
    name = raw.strip().upper()
    name = _PAREN_RE.sub("", name)
    for s in _SUFFIX_DETAIL:
        name = re.sub(s + r"$", "", name)
    return name


def _strip_bodies(name: str) -> str:
    for body in ["控股股份有限公司", "股份有限公司", "集团", "有限公司", "公司"]:
        if name.endswith(body):
            return name[: -len(body)]
    return name


_INDUSTRY_HEADS = [
    "技术", "科技", "信息", "电子", "数码", "网络", "软件", "智能", "汽车", "通信",
    "生物", "食品", "饮料", "乳业", "服饰", "体育", "珠宝", "日化", "家电", "控股",
    "物流", "连锁", "能源", "航空", "文化", "传媒",
]


def match_key(raw: str, key: str) -> bool:
    norm = normalize_company(raw)
    if not norm.startswith(key):
        return False
    rest = _strip_bodies(norm[len(key):])
    if not rest:
        return True
    if len(rest) <= 6:
        return True
    return any(rest.startswith(h) for h in _INDUSTRY_HEADS)


def strip_bodies(name: str) -> str:
    return _strip_bodies(normalize_company(name))