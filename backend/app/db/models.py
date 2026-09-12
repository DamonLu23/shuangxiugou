from sqlalchemy import (Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

LEVEL_NAMES = {
    1: "严格双休",
    2: "双休",
    3: "大小周",
    4: "单休",
    5: "996",
    6: "待验证",
}


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    biz_license_no = Column(String(32), unique=True, index=True, nullable=True)
    level = Column(Integer, default=6, index=True)          # L1 ~ L6
    confidence = Column(Float, default=0.0)                  # 0 ~ 1
    disputed = Column(Boolean, default=False)                # 多源矛盾标记
    updated_at = Column(DateTime, default=datetime.utcnow)
    next_recheck_at = Column(Date, nullable=True)

    brands = relationship("Brand", back_populates="company")
    evidences = relationship("Evidence", back_populates="company")


class Brand(Base):
    __tablename__ = "brands"
    __table_args__ = (Index("ix_brand_normalized", "normalized_name"),)

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    normalized_name = Column(String(128), nullable=False)   # 归一化后的品牌名（匹配用）
    aliases = Column(Text, default="")                       # JSON 别名列表
    company_id = Column(Integer, ForeignKey("companies.id"))
    verified = Column(Boolean, default=False)                # 人工校对标记

    company = relationship("Company", back_populates="brands")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    platform = Column(String(16), nullable=False)            # taobao / jd / pdd
    item_id = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    image = Column(String(512))
    price = Column(Float)
    brand_name = Column(String(128), index=True)             # 标题提取/接口给的品牌
    category = Column(String(64), index=True)
    click_url = Column(Text)                                 # 联盟跳转链接
    created_at = Column(DateTime, default=datetime.utcnow)


class Evidence(Base):
    __tablename__ = "evidences"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    source_type = Column(String(16))        # job_post / review / ugc_offer / ugc_contract / official
    url = Column(Text)
    keywords = Column(Text)                 # 命中的信号词列表
    raw_score = Column(Float)               # 关键词打分
    weight = Column(Float)                  # 来源权重
    collected_at = Column(Date)
    reviewed = Column(Boolean, default=False)

    company = relationship("Company", back_populates="evidences")


class UgcReport(Base):
    """用户上报的双休证据（待审核队列，审核通过后转入 Evidence）。"""

    __tablename__ = "ugc_reports"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    source_type = Column(String(16))        # ugc_offer / ugc_contract / ugc_other
    description = Column(Text)              # 用户填写的工时描述（如「合同约定做五休二」）
    image_url = Column(String(512))         # 可选：截图地址（打码后）
    status = Column(String(16), default="pending")  # pending / approved / rejected
    reviewer_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    company = relationship("Company")


class Job(Base):
    """岗位数据（求职搜索用；仅白名单 L1/L2 企业岗位对外展示）。"""

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    title = Column(String(256), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    company_name = Column(String(128), index=True)
    city = Column(String(64), index=True)
    tags = Column(Text, default="")          # 福利标签（双休/五险一金…）
    salary = Column(String(64), default="")  # 列表页薪资常被遮掩，存文本
    url = Column(Text)                       # 岗位原始链接
    source = Column(String(16), default="zhaopin")  # zhaopin / ugc
    collected_at = Column(Date)
    active = Column(Boolean, default=True, index=True)

    company = relationship("Company")


class Appeal(Base):
    """企业申诉（白名单更正/删除请求，48h 处理承诺）。"""

    __tablename__ = "appeals"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), index=True)
    contact = Column(String(128), default="")       # 联系人/邮箱（可空）
    reason = Column(Text, nullable=False)           # 申诉事由
    evidence_url = Column(String(512), default="")  # 官方制度/合同等公开链接
    status = Column(String(16), default="open")     # open / resolved / rejected
    handler_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    handled_at = Column(DateTime, nullable=True)

    company = relationship("Company")