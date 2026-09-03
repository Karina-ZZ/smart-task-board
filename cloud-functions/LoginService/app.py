"""LoginService Flask cloud-function entrypoint."""

from __future__ import annotations

from uuid import uuid4

from flask import Flask, jsonify, request

from services.auth_service import login_by_phone, request_sms

app = Flask(__name__)


def ok(data, status=200):
    return jsonify({"success": True, "data": data, "requestId": str(uuid4())}), status


def fail(message: str, code: str, status=400):
    return jsonify({"success": False, "error": {"code": code, "message": message}, "requestId": str(uuid4())}), status


@app.get("/health")
def health():
    return ok({"service": "LoginService", "status": "ok"})


@app.post("/sms/code")
def sms_code():
    payload = request.get_json(silent=True) or {}
    try:
        return ok(request_sms(payload.get("phone", "")), 201)
    except ValueError as exc:
        return fail(str(exc), "SMS_REQUEST_INVALID", 422)
    except RuntimeError:
        return fail("短信服务暂时不可用，请稍后重试", "SMS_PROVIDER_UNAVAILABLE", 503)


@app.post("/login/phone")
def phone_login():
    payload = request.get_json(silent=True) or {}
    try:
        return ok(login_by_phone(payload.get("phone", ""), payload.get("code", "")))
    except ValueError as exc:
        return fail(str(exc), "PHONE_LOGIN_FAILED", 401)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def fallback(path):
    return fail(f"Unknown path: /{path}", "NOT_FOUND", 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000)
