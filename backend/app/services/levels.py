"""双休等级聚合算法。

置信度 = Σ(来源权重 × 时间衰减)  归一化到 0~1。
等级由各证据 raw_score 加权聚合后落在阈值区间。
"""

from datetime import date
from typing import List, Optional

LEVEL_NAMES = {
    1: "严格双休",
    2: "双休",
    3: "大小周",
    4: "单休",
    5: "996",
    6: "待验证",
}

# 来源权重：合同/offer > 员工口碑(review) > 招聘描述(job_post 虚标常见) > 宣传软文(权重极低) > 官方宣传
# 权重在证据入库时写入 Evidence.weight（快照），聚合以入库值为准；此处为写入时的权威来源
SOURCE_WEIGHTS = {
    "ugc_contract": 1.0,
    "ugc_offer": 0.9,
    "review": 0.9,
    "job_post": 0.4,
    "official": 0.3,
    "review_promo": 0.1,
    "ugc_other": 0.5,   # 口头描述，无凭证
}

DEFAULT_WEIGHT = 0.5


def weight_for(source_type: str) -> float:
    """证据入库时取权重快照。"""
    return SOURCE_WEIGHTS.get(source_type, DEFAULT_WEIGHT)

MAX_DAYS = 365


def time_decay(collected_at: date, today: Optional[date] = None) -> float:
    """90 天内全权重，1 年后衰减到 ~0.6。"""
    today = today or date.today()
    days = (today - collected_at).days
    if days < 0:
        return 1.0
    if days > MAX_DAYS:
        days = MAX_DAYS
    return 1.0 - 0.4 * (days / MAX_DAYS)


def score_to_level(raw_score: float) -> int:
    if raw_score >= 1.5:
        return 1
    if raw_score >= 0.5:
        return 2
    if raw_score >= -0.5:
        return 3
    if raw_score >= -1.5:
        return 4
    return 5


def aggregate(evidences: List[dict], disputed: bool = False) -> tuple[int, float]:
    """evidences: [{raw_score, weight, collected_at, source_type}]

    weight 为入库时的来源权重快照；缺省时按 source_type 查 SOURCE_WEIGHTS（兼容旧调用）。
    """
    if not evidences or disputed:
        return 6, 0.0

    total_w = 0.0
    acc = 0.0
    for e in evidences:
        d = time_decay(e["collected_at"])
        w = e.get("weight") or SOURCE_WEIGHTS.get(e.get("source_type"), DEFAULT_WEIGHT)
        w = w * d
        total_w += w
        acc += e["raw_score"] * w

    if total_w <= 0:
        return 6, 0.0
    raw = acc / total_w
    level = score_to_level(raw)
    confidence = min(1.0, total_w / 3.0)  # 3 个等权重来源 ≈ 满信任
    return level, confidence


def recalc_company(company, session) -> None:
    """重算单个企业的等级与置信度（新证据入库 / UGC 审核通过后调用）。"""
    from ..db.models import Evidence

    evs = session.query(Evidence).filter(Evidence.company_id == company.id).all()
    docs = [{
        "raw_score": e.raw_score,
        "weight": e.weight,
        "collected_at": e.collected_at,
        "source_type": e.source_type,
    } for e in evs]
    level, confidence = aggregate(docs, disputed=company.disputed)
    company.level = level
    company.confidence = confidence