"""采集源抽象：统一产出 RawEvidence 原始记录。

只保存【来源链接 + 命中关键词 + 日期 + 打分 + 摘要】，不保存岗位/帖子原文全文。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RawEvidence:
    company_key: str          # 归一化后的公司主键（与种子表对应，如 华为）
    company_raw: str          # 原始公司名（如 华为技术有限公司北京研究所）
    source_type: str          # job_post / review / ugc_offer / ugc_contract / official
    url: str
    title: str = ""           # 岗位标题 / 帖子标题
    snippet: str = ""         # 片段（存摘要，不存全文）
    keywords: list = field(default_factory=list)
    raw_score: float = 0.0
    collected_at: date = field(default_factory=date.today)


class Source(ABC):
    source_type = "job_post"

    @abstractmethod
    async def fetch(self, keyword: str) -> list[RawEvidence]:
        """keyword: 种子表中的公司主键（如 华为）。"""
        ...