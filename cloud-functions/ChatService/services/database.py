"""Optional MySQL observability for ChatService. Business task truth is not stored here."""

from __future__ import annotations

from datetime import datetime, UTC
import json
from typing import Any

import config


def enabled() -> bool:
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


def ensure_chat_session(
    chat_session_id: str,
    scene: str,
    external_user_key: str | None,
    model: str,
) -> None:
    if not enabled():
        return
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_sessions
                (chat_session_id, external_user_key, scene, status, model_name)
            VALUES (%s, %s, %s, 'active', %s)
            ON DUPLICATE KEY UPDATE updated_at=CURRENT_TIMESTAMP(3), model_name=VALUES(model_name)
            """,
            (chat_session_id, external_user_key, scene, model),
        )
        conn.commit()


def save_message(
    chat_session_id: str,
    role: str,
    content: str,
    structured: Any = None,
    model: str | None = None,
) -> None:
    if not enabled():
        return
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chat_messages (chat_session_id, role, content, structured_json, model_name)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                chat_session_id,
                role,
                content,
                json.dumps(structured, ensure_ascii=False)
                if structured is not None
                else None,
                model,
            ),
        )
        conn.commit()


def save_llm_log(
    request_id: str,
    chat_session_id: str,
    request_type: str,
    status: str,
    *,
    latency_ms: int | None = None,
    error_message: str | None = None,
) -> None:
    if not enabled():
        return
    with _connection() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO llm_request_logs
                (
                    llm_request_id,
                    chat_session_id,
                    provider,
                    model_name,
                    request_type,
                    status,
                    latency_ms,
                    error_message,
                    completed_at,
                )
            VALUES (%s, %s, 'qwen', %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status=VALUES(status), latency_ms=VALUES(latency_ms),
                error_message=VALUES(error_message), completed_at=VALUES(completed_at)
            """,
            (
                request_id, chat_session_id, config.QWEN_MODEL, request_type, status,
                latency_ms, (error_message or "")[:1000] or None,
                datetime.now(UTC) if status in {"succeeded", "failed"} else None,
            ),
        )
        conn.commit()
