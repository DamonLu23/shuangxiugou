from pathlib import Path

from pydantic_settings import BaseSettings

DATA_DB = str(Path(__file__).resolve().parents[2] / "data" / "shuangxiugou.db")


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DB}"
    redis_url: str = "redis://localhost:6379/0"
    admin_token: str = "changeme-admin-token"  # 审核接口鉴权，部署前必须改
    # debug=True 允许默认 admin_token；生产必须 False 且改密钥
    debug: bool = True
    # 反馈 → GitHub Issue 无感通道（未配置则降级为本地队列）
    github_token: str = ""
    github_repo: str = "DamonLu23/shuangxiugou"


settings = Settings()


def validate_runtime_config() -> list[str]:
    """启动时配置校验。返回警告列表；生产模式配置不合法直接抛错。"""
    warnings = []
    if settings.debug and settings.admin_token == "changeme-admin-token":
        warnings.append("admin_token 仍为默认值，仅限本地开发！")

    if not settings.debug and settings.admin_token == "changeme-admin-token":
        raise RuntimeError(
            "生产模式禁止使用默认 admin_token，请通过环境变量 ADMIN_TOKEN 设置强随机值")
    return warnings