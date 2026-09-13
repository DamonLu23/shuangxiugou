"""反馈 → GitHub Issue 无感通道。

用户在线版表单提交（报岗位/申诉/纠错）后，后端将内容转成 GitHub Issue，
用户无需打开 GitHub、无需账号。

安全与降级：
- 未配置 GITHUB_TOKEN：优雅降级（数据仍入本地审核队列），返回 None
- 配置了 token 但 GitHub 请求失败：捕获异常降级，不阻塞主流程
- token 仅存服务端 .env（fine-grained PAT，仅 Issues: Write 权限）
"""

from typing import Optional

import httpx

from ..config import settings

KIND_META = {
    "job-report": {"label": "job-report", "title": "【报岗位】"},
    "appeal": {"label": "appeal", "title": "【申诉】"},
    "correction": {"label": "correction", "title": "【纠错】"},
}


def _render(kind: str, payload: dict) -> tuple[str, str]:
    """按 Issue 模板字段拼装标题与正文。"""
    meta = KIND_META[kind]
    if kind == "job-report":
        title = f"{meta['title']}{payload.get('company_name', '')} - {payload.get('title', '')}"
        body = "\n".join([
            f"**公司全名**：{payload.get('company_name', '')}",
            f"**岗位名称**：{payload.get('title', '')}",
            f"**城市**：{payload.get('city', '')}",
            f"**薪资**：{payload.get('salary', '')}",
            f"**岗位链接**：{payload.get('url', '')}",
            "",
            "_由双休购在线表单自动创建（用户无需 GitHub 账号）_",
        ])
    elif kind == "appeal":
        title = f"{meta['title']}{payload.get('company_name', '')}"
        body = "\n".join([
            f"**企业全名**：{payload.get('company_name', '')}",
            f"**申诉类型**：{payload.get('appeal_type', '更正信息')}",
            f"**事由**：{payload.get('reason', '')}",
            f"**证据链接**：{payload.get('evidence_url', '')}",
            f"**联系人**：{payload.get('contact', '')}",
            "",
            "_由双休购在线表单自动创建；处理承诺 48h（见 APPEAL.md）_",
        ])
    else:  # correction
        title = f"{meta['title']}{payload.get('subject', '')}"
        body = "\n".join([
            f"**数据类别**：{payload.get('target', '企业档案')}",
            f"**涉及对象**：{payload.get('subject', '')}",
            f"**问题描述**：{payload.get('detail', '')}",
            "",
            "_由双休购在线表单自动创建_",
        ])
    return title, body


async def _post_issue(kind: str, payload: dict) -> str:
    """真实调用 GitHub REST API（测试通过 monkeypatch 此函数 mock）。"""
    meta = KIND_META[kind]
    title, body = _render(kind, payload)
    url = f"https://api.github.com/repos/{settings.github_repo}/issues"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "body": body, "labels": [meta["label"]]},
        )
        resp.raise_for_status()
        return resp.json()["html_url"]


async def create_issue(kind: str, payload: dict) -> Optional[str]:
    """创建 Issue，返回 html_url；未配置 token 或失败时返回 None（优雅降级）。"""
    if kind not in KIND_META:
        raise ValueError(f"未知反馈类型: {kind}")
    if not settings.github_token:
        return None
    try:
        return await _post_issue(kind, payload)
    except Exception as e:
        print(f"[反馈] GitHub Issue 创建失败（已降级为本地队列）: {type(e).__name__} {str(e)[:120]}")
        return None