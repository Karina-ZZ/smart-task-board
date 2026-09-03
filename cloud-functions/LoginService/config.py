"""LoginService environment configuration. No secret is hard-coded in source."""

from __future__ import annotations

import os


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


APP_ENV = env("APP_ENV", "development")
SMS_PROVIDER = env("SMS_PROVIDER", "mock")
SMS_CODE_TTL_SECONDS = int(env("SMS_CODE_TTL_SECONDS", "300"))
SMS_CODE_HASH_SECRET = env("SMS_CODE_HASH_SECRET", "development-only-change-me")
JWT_SECRET = env("CLOUD_JWT_SECRET", "development-only-change-me-please")
JWT_ISSUER = env("CLOUD_JWT_ISSUER", "wangxu-cloud-login")
JWT_AUDIENCE = env("CLOUD_JWT_AUDIENCE", "wangxu-cloud-chat")
JWT_EXPIRE_SECONDS = int(env("CLOUD_JWT_EXPIRE_SECONDS", "7200"))

MYSQL_HOST = env("MYSQL_HOST")
MYSQL_PORT = int(env("MYSQL_PORT", "3306"))
MYSQL_DATABASE = env("MYSQL_DATABASE")
MYSQL_USER = env("MYSQL_USER")
MYSQL_PASSWORD = env("MYSQL_PASSWORD")

ALIYUN_ACCESS_KEY_ID = env("ALIYUN_ACCESS_KEY_ID")
ALIYUN_ACCESS_KEY_SECRET = env("ALIYUN_ACCESS_KEY_SECRET")
ALIYUN_DYPN_ENDPOINT = env("ALIYUN_DYPN_ENDPOINT", "dypnsapi.aliyuncs.com")
ALIYUN_SMS_SIGN_NAME = env("ALIYUN_SMS_SIGN_NAME")
ALIYUN_SMS_TEMPLATE_CODE = env("ALIYUN_SMS_TEMPLATE_CODE")


def validate_production_config() -> None:
    if APP_ENV.casefold() != "production":
        return
    if SMS_PROVIDER == "mock":
        raise RuntimeError("SMS_PROVIDER=mock is forbidden in production")
    if SMS_CODE_HASH_SECRET.startswith("development-") or JWT_SECRET.startswith("development-"):
        raise RuntimeError("production SMS/JWT secrets must be provided by environment variables")
    if not all([MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER]):
        raise RuntimeError("production LoginService requires MySQL configuration")


validate_production_config()
