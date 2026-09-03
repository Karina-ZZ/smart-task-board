"""LoginService persistence backed by MySQL 8.0, with an in-memory local fallback."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import config

_MEMORY_CODES: dict[str, dict[str, Any]] = {}
_MEMORY_USERS: dict[str, int] = {}
_MEMORY_SESSIONS: dict[str, dict[str, Any]] = {}


def mysql_enabled() -> bool:
    return all([config.MYSQL_HOST, config.MYSQL_DATABASE, config.MYSQL_USER])


def _connection():
    import pymysql

    return pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def save_sms_code(phone: str, code_hash: str, expires_at: datetime, provider_request_id: str | None) -> None:
    if not mysql_enabled():
        _MEMORY_CODES[phone] = {
            "code_hash": code_hash,
            "expires_at": expires_at,
            "verify_status": "pending",
            "attempt_count": 0,
            "max_attempts": 5,
        }
        return
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sms_verification_codes
                (phone, purpose, code_hash, provider_request_id, send_status, verify_status, expires_at)
            VALUES (%s, 'login', %s, %s, 'sent', 'pending', %s)
            """,
            (phone, code_hash, provider_request_id, expires_at),
        )
        conn.commit()


def latest_sms_code(phone: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        return _MEMORY_CODES.get(phone)
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT sms_code_id, code_hash, expires_at, verify_status, attempt_count, max_attempts
            FROM sms_verification_codes
            WHERE phone=%s AND purpose='login'
            ORDER BY created_at DESC LIMIT 1
            """,
            (phone,),
        )
        return cursor.fetchone()


def mark_sms_attempt(phone: str, *, verified: bool, locked: bool = False) -> None:
    if not mysql_enabled():
        record = _MEMORY_CODES.get(phone)
        if record:
            record["attempt_count"] += 1
            record["verify_status"] = "verified" if verified else ("locked" if locked else "pending")
        return
    status = "verified" if verified else ("locked" if locked else "pending")
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            UPDATE sms_verification_codes
            SET attempt_count=attempt_count+1, verify_status=%s,
                verified_at=CASE WHEN %s='verified' THEN CURRENT_TIMESTAMP(3) ELSE verified_at END
            WHERE sms_code_id=(
                SELECT sms_code_id FROM (
                    SELECT sms_code_id FROM sms_verification_codes
                    WHERE phone=%s AND purpose='login' ORDER BY created_at DESC LIMIT 1
                ) latest
            )
            """,
            (status, status, phone),
        )
        conn.commit()


def upsert_user(phone: str) -> int:
    if not mysql_enabled():
        if phone not in _MEMORY_USERS:
            _MEMORY_USERS[phone] = len(_MEMORY_USERS) + 1
        return _MEMORY_USERS[phone]
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cloud_users (phone, status, last_login_at)
            VALUES (%s, 'active', CURRENT_TIMESTAMP(3))
            ON DUPLICATE KEY UPDATE last_login_at=CURRENT_TIMESTAMP(3), updated_at=CURRENT_TIMESTAMP(3)
            """,
            (phone,),
        )
        cursor.execute("SELECT user_id FROM cloud_users WHERE phone=%s", (phone,))
        user_id = int(cursor.fetchone()["user_id"])
        conn.commit()
        return user_id


def save_login_session(session_id: str, user_id: int, jti: str, issued_at: datetime, expires_at: datetime) -> None:
    if not mysql_enabled():
        _MEMORY_SESSIONS[session_id] = {"user_id": user_id, "jti": jti, "expires_at": expires_at}
        return
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO login_sessions (session_id, user_id, jwt_jti, issued_at, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session_id, user_id, jti, issued_at, expires_at),
        )
        conn.commit()
