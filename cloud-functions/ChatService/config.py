"""ChatService configuration loaded from a dedicated secret env file or process environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHAT_ENV_FILE = REPOSITORY_ROOT / "secrets" / "chatservice.env"
CHAT_ENV_FILE_VARIABLE = "WANGXU_CHAT_ENV_FILE"


def resolve_chat_env_file() -> Path:
    """Return the explicit server override or the repository-local ChatService env path."""

    configured = os.getenv(CHAT_ENV_FILE_VARIABLE, "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_CHAT_ENV_FILE


# Do not override real process environment variables; deployment platforms can inject secrets safely.
load_dotenv(resolve_chat_env_file(), override=False)


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


APP_ENV = env("APP_ENV", "development")
CHAT_REQUIRE_AUTH = env("CHAT_REQUIRE_AUTH", "false").casefold() == "true"
JWT_SECRET = (
    env("CHAT_SERVICE_JWT_SECRET_KEY")
    or env("WANGXU_AI_JWT_SECRET")
    or "development-only-change-me-please"
)
JWT_ISSUER = env("CHAT_SERVICE_JWT_ISSUER") or env(
    "WANGXU_AI_JWT_ISSUER",
    "smart-task-board",
)
JWT_AUDIENCE = env("CHAT_SERVICE_JWT_AUDIENCE") or env(
    "WANGXU_AI_JWT_AUDIENCE",
    "wangxu-chat",
)
JWT_REQUIRED_SCOPE = "task-intake"

QWEN_API_KEY = env("QWEN_API_KEY") or env("DASHSCOPE_API_KEY")
QWEN_BASE_URL = env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = env("QWEN_MODEL", "qwen-plus")
QWEN_ASR_MODEL = env("QWEN_ASR_MODEL")
QWEN_TIMEOUT_SECONDS = int(env("QWEN_TIMEOUT_SECONDS", "30"))

MYSQL_HOST = env("MYSQL_HOST")
MYSQL_PORT = int(env("MYSQL_PORT", "3306"))
MYSQL_DATABASE = env("MYSQL_DATABASE")
MYSQL_USER = env("MYSQL_USER")
MYSQL_PASSWORD = env("MYSQL_PASSWORD")


def validate_production_config() -> None:
    if APP_ENV.casefold() != "production":
        return
    if not QWEN_API_KEY:
        raise RuntimeError("production ChatService requires QWEN_API_KEY or DASHSCOPE_API_KEY")
    if not CHAT_REQUIRE_AUTH:
        raise RuntimeError("production ChatService requires CHAT_REQUIRE_AUTH=true")
    if len(JWT_SECRET) < 32 or JWT_SECRET.startswith("development-"):
        raise RuntimeError("production ChatService requires CHAT_SERVICE_JWT_SECRET_KEY")


validate_production_config()
