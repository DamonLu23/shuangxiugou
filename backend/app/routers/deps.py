"""路由共享依赖：管理鉴权 / UGC 限流（避免各 router 重复实现）。"""

import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException

from ..config import settings


def require_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != settings.admin_token:
        raise HTTPException(403, "无管理权限")
    return True


# UGC 上报限流：每 IP 每小时 N 条（内存滑窗，单实例够用；多实例换 Redis）
RATE_LIMIT = 5
RATE_WINDOW = 3600
_report_times: dict[str, deque] = defaultdict(deque)


def check_rate_limit(ip: str):
    now = time.monotonic()
    window = _report_times[ip]
    while window and now - window[0] > RATE_WINDOW:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(429, "提交过于频繁，请稍后再试（每小时最多 5 条）")
    window.append(now)