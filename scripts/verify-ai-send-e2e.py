#!/usr/bin/env python3
"""Test14: real HTTP F1/F2 verification on an explicitly isolated local backend.

Login -> empty-source draft -> send -> dashboard/list/detail/actions; validates
null/legal/illegal report cycles. No HTTP mocks, migrations, cleanup or AI call.
This is NOT a mini-program UI or real-Qwen acceptance test.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

BASE_URL = os.getenv("STB_E2E_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
CREATOR = os.getenv("STB_E2E_CREATOR", "E-CREATOR")
ASSIGNEE = os.getenv("STB_E2E_ASSIGNEE", "E-ASSIGNEE")
REPORTER = os.getenv("STB_E2E_REPORTER", "E-REVIEWER")
REVIEWER = os.getenv("STB_E2E_REVIEWER", "E-REVIEWER")


def require_isolated_target() -> None:
    parsed = urlparse(BASE_URL)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
            or parsed.username or parsed.password or parsed.path or parsed.query):
        raise RuntimeError("This write probe only supports a local isolated HTTP backend")
    if os.getenv("STB_TEST14_ALLOW_TEST_WRITES") != "1":
        raise RuntimeError(
            "Set STB_TEST14_ALLOW_TEST_WRITES=1 only after verifying the backend uses "
            "an isolated disposable database (not an existing demo or production database)"
        )


def request_json(path, method="GET", body=None, token=None, headers=None):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request_headers.update(headers or {})
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=payload, method=method, headers=request_headers,
    )
    # Loopback requests must not be routed through a corporate/system proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        response = opener.open(req, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        content = response.read().decode("utf-8")
        return response.code, json.loads(content) if content else None


def checked(path, method="GET", body=None, token=None, expected=200, headers=None):
    status, result = request_json(path, method, body, token, headers)
    if status != expected:
        code = (result or {}).get("error", {}).get("code", "unexpected_response")
        # Do not print credentials, arbitrary response bodies, or token-bearing objects.
        raise AssertionError(f"{method} {path}: expected {expected}, got {status} ({code})")
    return result


def draft_payload(cycle):
    now = datetime.now(UTC).replace(microsecond=0)
    task_id = str(uuid4())
    return {
        "task_id": task_id, "task_name": f"Test14-{task_id[:8]}",
        "task_description": "Test14 complete fields without submitting AI clarification",
        "task_goal": "Send and return to creator workbench without a 500",
        "task_source": None,
        "main_assignee_employee_no": ASSIGNEE, "report_to_employee_no": REPORTER,
        "reviewer_employee_no": REVIEWER, "start_time": now.isoformat(),
        "deadline": (now + timedelta(days=2)).isoformat(), "task_weight": 3,
        "report_cycle": cycle, "participants": [], "extraction_record_ids": [],
    }


def assert_reads(token, task_id):
    for path, field in [("/api/v1/dashboard/summary", "recent_tasks"),
                        ("/api/v1/tasks?relation=created", "items")]:
        response = checked(path, token=token)
        matching = [row for row in response[field] if row["task_id"] == task_id]
        assert len(matching) == 1, "Sent task was silently dropped from the response"
        assert "reassign_task" in matching[0]["allowed_actions"]
    actions = checked(f"/api/v1/tasks/{task_id}/available-actions", token=token)
    assert "reassign_task" in actions["allowed_actions"]
    checked("/api/v1/tasks/inbox", token=token)


def send_scenario(token, cycle):
    payload = draft_payload(cycle)
    created = checked("/api/v1/tasks", "POST", payload, token, 201)
    task_id = created["task_id"]
    detail_path = f"/api/v1/tasks/{task_id}"
    for invalid in ("weekly", "\u6bcf\u5468", "weekly:MON@24:00"):
        checked(f"{detail_path}/draft", "PATCH", {
            "expected_task_version": created["task_version"], "report_cycle": invalid,
            "task_name": "MUST NOT BE SAVED",
        }, token, 422)
        detail = checked(detail_path, token=token)
        assert detail["report_cycle"] == cycle
        assert detail["task_version"] == created["task_version"]
        assert detail["task_name"] == payload["task_name"]
    submitted = checked(f"{detail_path}/actions/submit-for-confirmation", "POST",
                        {"expected_task_version": created["task_version"]}, token)
    body = {"expected_task_version": submitted["task_version"]}
    headers = {"Idempotency-Key": f"test14-send-{task_id}"}
    sent = checked(f"{detail_path}/actions/confirm-and-send", "POST", body, token, headers=headers)
    repeated = checked(f"{detail_path}/actions/confirm-and-send", "POST", body, token,
                       headers=headers)
    assert sent == repeated
    assert sent["status"] in {"pending_acceptance", "pending_accept"}
    detail = checked(detail_path, token=token)
    assert detail["task_source"] is None and detail["report_cycle"] == cycle
    assert not detail["nodes"]
    assert_reads(token, task_id)
    return {"task_id": task_id, "status": detail["status"], "report_cycle": cycle}


def main() -> int:
    require_isolated_target()
    login = checked("/api/v1/auth/login", "POST", {"employee_no": CREATOR})
    token = login["access_token"]
    assert checked("/api/v1/me", token=token)["employee_no"] == CREATOR
    for invalid in ("weekly", "\u6bcf\u5468"):
        checked("/api/v1/tasks", "POST", draft_payload(invalid), token, 422)
    results = [send_scenario(token, cycle) for cycle in (None, "weekly:MON@09:00")]
    print("TEST14_REAL_HTTP_PASS")
    print("AI_SEND_REAL_HTTP_E2E_PASS (HTTP only; UI/real AI not tested by this script)")
    print(json.dumps({"tasks": results}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TEST14_REAL_HTTP_FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
