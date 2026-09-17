"""榜单名录源：公开排行榜 → 企业种子候选（纯解析，不触网）。

- 《财富》中国500强 / 世界500强：静态 HTML 表格（table#table1）
- 新增榜单：写一个解析函数（html → [{rank, full_name, country}]）并在
  LIST_SOURCES 注册（url + parser + note），fetch_lists.py 自动支持
- 产物种子字段：key（品牌检索名）/ full_name（企业全名）/ category（暂空）

配合 crawler/fetch_lists.py 生成 data/companies/seed_extra.csv，
再由 crawler/expand_seed.py 幂等合并进 seed.csv。
"""

from __future__ import annotations

import re

_TABLE_RE = re.compile(r'<table[^>]*id="table1".*?</table>', re.S | re.I)
_GENERIC_TABLE_RE = re.compile(r"<table.*?</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_EN_PAREN_RE = re.compile(r"[（(][A-Za-z0-9&.,'\s\-]+[）)]")
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 企业名后缀（按长度优先剥离，循环直到稳定）
_CORP_SUFFIXES = [
    "控股股份有限公司", "集团股份有限公司", "有限责任公司", "股份有限公司",
    "集团有限公司", "控股有限公司", "有限公司", "控股集团", "集团公司",
    "集团", "控股", "公司",
]


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", html)).strip()


def cn_name(raw: str) -> str:
    """去英文括号（如「亚马逊（AMAZON.COM)」→「亚马逊」），保留中文括号。"""
    name = _EN_PAREN_RE.sub("", raw).strip()
    return name or raw.strip()


def parse_ranked_table(html: str) -> list[dict]:
    """解析榜单静态表格 → [{rank, name, cells}]。

    两个榜单均为 table#table1；含 <a> 的单元格为名称列。
    """
    m = _TABLE_RE.search(html)
    if not m:
        return []
    rows = []
    for row_html in _ROW_RE.findall(m.group(0)):
        raw_tds = _TD_RE.findall(row_html)
        cells = [_text(c) for c in raw_tds]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        name = ""
        for c_html in raw_tds:
            if "<a " in c_html.lower():
                name = cn_name(_text(c_html))
                break
        if not name:
            continue
        rows.append({"rank": int(cells[0]), "name": name, "cells": cells})
    return rows


def parse_fortune_global500(html: str) -> list[dict]:
    """《财富》世界500强：只取中国公司（国家列 = 中国）。"""
    out = []
    for r in parse_ranked_table(html):
        country = r["cells"][4] if len(r["cells"]) > 4 else ""
        if not country.startswith("中国"):
            continue
        out.append({"rank": r["rank"], "full_name": r["name"], "country": country})
    return out


def parse_fortune_china500(html: str) -> list[dict]:
    """《财富》中国500强：全部为中国公司（含港澳台）。"""
    return [{"rank": r["rank"], "full_name": r["name"], "country": "中国"}
            for r in parse_ranked_table(html)]


def parse_plain_ranked_table(html: str, min_rows: int = 100) -> list[dict]:
    """通用榜单表格解析（表头含「企业名称」的普通 <table>，名称列无链接）。

    适配中企联榜单这类纯文本表格；返回行数最多的合格表格。
    """
    best: list[dict] = []
    for table in _GENERIC_TABLE_RE.findall(html):
        rows, header_ok = [], False
        for row_html in _ROW_RE.findall(table):
            cells = [_text(c) for c in _TD_RE.findall(row_html)]
            if not cells:
                continue
            if any("企业名称" in c for c in cells):
                header_ok = True
                continue
            if header_ok and len(cells) >= 2 and cells[0].isdigit():
                rows.append({"rank": int(cells[0]), "name": cells[1], "cells": cells})
        if len(rows) > len(best):
            best = rows
    return best if len(best) >= min_rows else []


def parse_cnenterprise500(html: str) -> list[dict]:
    """中企联《中国企业500强》：全为中国公司（纯文本表格）。"""
    return [{"rank": r["rank"], "full_name": r["name"], "country": "中国"}
            for r in parse_plain_ranked_table(html)]


def parse_internet100(html: str) -> list[dict]:
    """中国互联网协会《中国互联网综合实力前百家企业》：前 5 家无序号（跳过）。"""
    return [{"rank": r["rank"], "full_name": r["name"], "country": "中国"}
            for r in parse_plain_ranked_table(html, min_rows=90)]


def derive_key(full_name: str) -> str:
    """企业全名 → 品牌检索 key（如「阿里巴巴集团控股有限公司」→「阿里巴巴」）。"""
    name = _PAREN_RE.sub("", full_name).strip()
    changed = True
    while changed:
        changed = False
        for s in _CORP_SUFFIXES:
            if name.endswith(s) and len(name) > len(s):
                name = name[: -len(s)].strip()
                changed = True
                break
    return name


def is_cjk_key(key: str) -> bool:
    """纯中文 key 才做模糊包含匹配（避免 ASCII 短 key 误伤）。"""
    return bool(key) and bool(_CJK_RE.search(key)) and not re.search(r"[A-Za-z0-9]", key)


def duplicate_reason(key: str, full_name: str,
                     keys: dict[str, str], names: set[str]) -> str | None:
    """与已知企业比对：同名 / 同 key / 疑似同品牌（中文包含关系）。"""
    if full_name in names:
        return "已有同名企业"
    if key in keys:
        return "已有同 key"
    if is_cjk_key(key):
        for k, n in keys.items():
            if len(k) >= 2 and is_cjk_key(k) and (k in key or key in k):
                return f"疑似与「{k}」（{n}）重复"
    return None


LIST_SOURCES = {
    "fortune-china500": {
        "url": "https://www.fortunechina.com/fortune500/c/2026-07/21/content_475181.htm",
        "parser": parse_fortune_china500,
        "note": "2026年《财富》中国500强",
    },
    "fortune-global500": {
        "url": "https://www.fortunechina.com/fortune500/c/2026-07/28/content_475298.htm",
        "parser": parse_fortune_global500,
        "note": "2026年《财富》世界500强（中国公司）",
    },
    "cnenterprise-500": {
        "url": "https://resource.emagecompany.com/china_500/2025china500.html",
        "parser": parse_cnenterprise500,
        "note": "中国企业联合会 2025中国企业500强（公开转载版，官方原版为图片）",
    },
    "internet-100": {
        "url": "https://www.cnpp.cn/focus/3535092.html",
        "parser": parse_internet100,
        "note": "中国互联网协会 2025互联网综合实力前百家企业（公开转载版）",
    },
}
