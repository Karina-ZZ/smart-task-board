"""Feature 05 task-field extraction and multi-round clarification orchestration."""

from __future__ import annotations

import time
from uuid import uuid4

import config

from services import database
from services.qwen_service import QwenService

FORBIDDEN_FIELDS = {"estimatedHours", "estimated_hours", "nodes", "dependencies"}


def _question_text(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("question") or item.get("label") or "").strip()
    return ""


def normalize_result(raw: dict[str, object]) -> dict[str, object]:
    task_draft = raw.get("taskDraft") or raw.get("task_draft") or {}
    if not isinstance(task_draft, dict):
        task_draft = {}
    task_draft = {key: value for key, value in task_draft.items() if key not in FORBIDDEN_FIELDS}
    for field in FORBIDDEN_FIELDS:
        task_draft.pop(field, None)
    missing = [
        str(item)
        for item in (raw.get("missingFields") or raw.get("missing_fields") or [])
        if str(item) not in FORBIDDEN_FIELDS
    ]
    low = [
        str(item)
        for item in (
            raw.get("lowConfidenceFields") or raw.get("low_confidence_fields") or []
        )
        if str(item) not in FORBIDDEN_FIELDS
    ]
    questions = [
        text
        for text in (
            _question_text(item)
            for item in (
                raw.get("confirmQuestions") or raw.get("confirm_questions") or []
            )
        )
        if text
    ]
    try:
        score = raw.get("confidenceScore", raw.get("confidence_score", 0)) or 0
        confidence = max(0.0, min(1.0, float(score)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "taskDraft": task_draft,
        "missingFields": list(dict.fromkeys(missing)),
        "lowConfidenceFields": list(dict.fromkeys(low)),
        "confirmQuestions": questions[:10],
        "confidenceScore": confidence,
    }


def run_intake(
    payload: dict[str, object],
    *,
    clarification: bool,
    qwen: QwenService | None = None,
    external_user_key: str | None = None,
) -> dict[str, object]:
    input_payload = payload.get("input")
    raw_text = (
        input_payload.get("rawText") or input_payload.get("asrText") or ""
        if isinstance(input_payload, dict)
        else ""
    )
    if not isinstance(input_payload, dict) or not str(raw_text).strip():
        raise ValueError("缺少任务描述文本")
    chat_session_id = str(
        payload.get("chatSessionId")
        or (payload.get("previousExtraction") or {}).get("chatSessionId")
        or uuid4()
    )
    scene = "task_field_clarification" if clarification else "task_field_extraction"
    database.ensure_chat_session(chat_session_id, scene, external_user_key, config.QWEN_MODEL)
    database.save_message(chat_session_id, "user", str(payload), model=config.QWEN_MODEL)
    request_id = str(uuid4())
    database.save_llm_log(request_id, chat_session_id, scene, "pending")
    started = time.perf_counter()
    try:
        raw = (qwen or QwenService()).task_intake(payload)
        result = normalize_result(raw)
        result.update({
            "chatSessionId": chat_session_id,
            "provider": "qwen",
            "model": config.QWEN_MODEL,
            "requestId": request_id,
        })
        latency = int((time.perf_counter() - started) * 1000)
        database.save_message(
            chat_session_id,
            "assistant",
            str(raw),
            structured=result,
            model=config.QWEN_MODEL,
        )
        database.save_llm_log(
            request_id, chat_session_id, scene, "succeeded", latency_ms=latency
        )
        return result
    except Exception as exc:
        latency = int((time.perf_counter() - started) * 1000)
        database.save_llm_log(
            request_id,
            chat_session_id,
            scene,
            "failed",
            latency_ms=latency,
            error_message=str(exc),
        )
        raise
