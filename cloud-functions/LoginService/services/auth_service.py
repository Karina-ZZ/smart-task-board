"""SMS-code verification and JWT issuing for LoginService."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

import config
from services import database, sms_service

PHONE_PATTERN = re.compile(r"^(?:\+?86)?1\d{10}$")


def normalize_phone(phone: str) -> str:
    value = re.sub(r"[\s-]", "", str(phone or ""))
    if not PHONE_PATTERN.match(value):
        raise ValueError("手机号格式不正确")
    if value.startswith("+86"):
        value = value[3:]
    elif value.startswith("86") and len(value) == 13:
        value = value[2:]
    return value


def _hash_code(phone: str, code: str) -> str:
    body = f"{phone}:{code}".encode()
    return hmac.new(config.SMS_CODE_HASH_SECRET.encode(), body, hashlib.sha256).hexdigest()


def request_sms(phone: str) -> dict[str, object]:
    normalized = normalize_phone(phone)
    code = sms_service.generate_code()
    request_id = sms_service.send_code(normalized, code)
    expires_at = datetime.now(UTC) + timedelta(seconds=config.SMS_CODE_TTL_SECONDS)
    database.save_sms_code(normalized, _hash_code(normalized, code), expires_at, request_id)
    result: dict[str, object] = {"phone": normalized, "expiresIn": config.SMS_CODE_TTL_SECONDS}
    if config.SMS_PROVIDER == "mock" and config.APP_ENV != "production":
        result["debugCode"] = code
    return result


def login_by_phone(phone: str, code: str) -> dict[str, object]:
    normalized = normalize_phone(phone)
    record = database.latest_sms_code(normalized)
    if not record or record.get("verify_status") != "pending":
        raise ValueError("验证码无效或已使用")
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise ValueError("验证码已过期")
    attempts = int(record.get("attempt_count") or 0)
    max_attempts = int(record.get("max_attempts") or 5)
    verified = hmac.compare_digest(str(record["code_hash"]), _hash_code(normalized, str(code or "")))
    if not verified:
        database.mark_sms_attempt(normalized, verified=False, locked=attempts + 1 >= max_attempts)
        raise ValueError("验证码错误")
    database.mark_sms_attempt(normalized, verified=True)

    user_id = database.upsert_user(normalized)
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=config.JWT_EXPIRE_SECONDS)
    session_id = str(uuid4())
    jti = str(uuid4())
    token = jwt.encode(
        {
            "sub": str(user_id), "phone": normalized, "jti": jti,
            "iss": config.JWT_ISSUER, "aud": config.JWT_AUDIENCE,
            "iat": issued_at, "exp": expires_at,
        },
        config.JWT_SECRET,
        algorithm="HS256",
    )
    database.save_login_session(session_id, user_id, jti, issued_at, expires_at)
    return {
        "token": token,
        "tokenType": "bearer",
        "expiresIn": config.JWT_EXPIRE_SECONDS,
        "user": {"userId": user_id, "phone": normalized},
    }
