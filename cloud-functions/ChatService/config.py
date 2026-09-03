"""ChatService environment configuration. Qwen/MySQL/AI-token secrets stay in cloud env vars."""

from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


APP_ENV = env("APP_ENV", "development")
CHAT_REQUIRE_AUTH = env("CHAT_REQUIRE_AUTH", "false").casefold() == "true"
JWT_SECRET = env("WANGXU_AI_JWT_SECRET", "development-only-change-me-please")
JWT_ISSUER = env("WANGXU_AI_JWT_ISSUER", "smart-task-board")
JWT_AUDIENCE = env("WANGXU_AI_JWT_AUDIENCE", "wangxu-chat")
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
        raise RuntimeError("production ChatService requires QWEN_API_KEY")
    if not CHAT_REQUIRE_AUTH:
        raise RuntimeError("production ChatService requires CHAT_REQUIRE_AUTH=true")
    if JWT_SECRET.startswith("development-"):
        raise RuntimeError("production ChatService requires WANGXU_AI_JWT_SECRET")


validate_production_config()
