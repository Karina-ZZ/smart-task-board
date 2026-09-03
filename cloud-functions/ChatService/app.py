"""ChatService Flask cloud-function entrypoint for Qwen task intake and clarification."""

from __future__ import annotations

from uuid import uuid4

from flask import Flask, jsonify, request

from services.auth import verify_bearer
from services.qwen_service import QwenService
from services.task_intake import run_intake

app = Flask(__name__)


def ok(data, status=200):
    return jsonify({"success": True, "data": data, "requestId": str(uuid4())}), status


def fail(message: str, code: str, status=400):
    return jsonify({"success": False, "error": {"code": code, "message": message}, "requestId": str(uuid4())}), status


def actor_key(claims, _payload):
    subject = claims.get("sub")
    return str(subject).strip() if subject else None


def authenticated_payload():
    claims = verify_bearer(request.headers.get("Authorization"))
    payload = request.get_json(silent=True) or {}
    return claims, payload


@app.get("/health")
def health():
    return ok({"service": "ChatService", "status": "ok"})


@app.post("/task-intake/extract")
def extract_task():
    try:
        claims, payload = authenticated_payload()
        return ok(run_intake(payload, clarification=False, external_user_key=actor_key(claims, payload)))
    except PermissionError as exc:
        return fail(str(exc), "CLOUD_AUTH_REQUIRED", 401)
    except ValueError as exc:
        return fail(str(exc), "TASK_INTAKE_INVALID", 422)
    except RuntimeError:
        return fail("大模型暂时不可用，请稍后重试", "QWEN_UNAVAILABLE", 503)


@app.post("/task-intake/clarify")
def clarify_task():
    try:
        claims, payload = authenticated_payload()
        if not isinstance(payload.get("clarificationAnswers"), dict):
            raise ValueError("缺少追问回答")
        return ok(run_intake(payload, clarification=True, external_user_key=actor_key(claims, payload)))
    except PermissionError as exc:
        return fail(str(exc), "CLOUD_AUTH_REQUIRED", 401)
    except ValueError as exc:
        return fail(str(exc), "TASK_CLARIFICATION_INVALID", 422)
    except RuntimeError:
        return fail("大模型暂时不可用，请稍后重试", "QWEN_UNAVAILABLE", 503)


@app.post("/task-intake/transcribe")
def transcribe():
    try:
        verify_bearer(request.headers.get("Authorization"))
        payload = request.get_json(silent=True) or {}
        audio = str(payload.get("audioBase64") or "").strip()
        if not audio:
            raise ValueError("缺少录音数据")
        text = QwenService().transcribe(audio, str(payload.get("fileName") or "voice.mp3"))
        return ok({"text": text})
    except PermissionError as exc:
        return fail(str(exc), "CLOUD_AUTH_REQUIRED", 401)
    except ValueError as exc:
        return fail(str(exc), "VOICE_INPUT_INVALID", 422)
    except RuntimeError as exc:
        return fail(str(exc), "ASR_UNAVAILABLE", 503)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def fallback(path):
    return fail(f"Unknown path: /{path}", "NOT_FOUND", 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
