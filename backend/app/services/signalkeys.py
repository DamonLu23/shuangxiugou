"""信号词库与打分（单一事实来源）。

crawler/scoring/keywords.py 仅为兼容 re-export，勿在此维护第二份词表。
"""

POSITIVE = [
    ("严格双休", 2.0), ("周末双休", 1.0), ("双休", 0.8), ("做五休二", 1.2),
    ("5天8小时", 1.2), ("五天八小时", 1.2), ("五天工作制", 1.5), ("双休制", 1.0),
    ("朝九晚五", 1.5), ("朝九晚六", 1.0), ("按时下班", 1.5),
    ("周末休息", 1.0), ("有双休", 1.0), ("双休日", 0.5),
    ("不加班", 1.0), ("不用加班", 1.0), ("无加班", 1.0),
    ("很少加班", 0.8), ("基本不加班", 1.0), ("几乎不加班", 1.0),
]
NEGATIVE = [
    ("996", -3.0), ("007", -3.0), ("全年无休", -3.0), ("做六休一", -2.0),
    ("单休", -2.0), ("周末单休", -2.5), ("月休四天", -2.0), ("月休4天", -2.0),
    ("大小周", -1.0), ("单双休", -1.0), ("调休", -1.0), ("弹性工作", -0.5),
    ("加班费", -0.5), ("两班倒", -1.0), ("三班倒", -1.0), ("夜班", -0.3),
    ("加班补贴", -0.5), ("加班", -0.8),
]

# 否定前缀：匹配「加班」前先剔除这些组合，避免「不加班」被扣分
OVERTIME_NEGATIONS = ("基本不", "几乎不", "很少", "不用", "无需", "没有", "不", "没", "无")


def score_job_description(text: str) -> tuple[float, list[str]]:
    """对文本按信号词打分，返回 (raw_score, hit_keywords)。
    「不加班/很少加班」等否定表达不触发「加班」负信号。"""
    cleaned = text
    for pref in overtime_neg():
        cleaned = cleaned.replace(pref + "加班", "")
    raw = 0.0
    matched = []
    for kw, s in POSITIVE:
        if kw in text:
            raw += s
            matched.append(kw)
    for kw, s in NEGATIVE:
        target = cleaned if kw == "加班" else text
        if kw in target:
            raw += s
            matched.append(kw)
    return raw, matched


def overtime_neg():
    return OVERTIME_NEGATIONS