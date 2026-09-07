#!/usr/bin/env python3
"""
Feature: real HTTP verification for task send without answering AI clarification.
Responsibilities:
- Login through the isolated Web prototype auth endpoint.
- Create a complete task draft with task_source omitted/null.
- Submit and confirm-send through the real FastAPI process.
- Fetch the task detail and assert pending_acceptance/pending_accept semantics.
Does not own: UI automation, database provisioning, migrations, or test-data seeding.
Hotfix: Feature16 Login + AI Clarification Gate verification.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = os.getenv("STB_E2E_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
CREATOR = os.getenv("STB_E2E_CREATOR", "E-CREATOR")
ASSIGNEE = os.getenv("STB_E2E_ASSIGNEE", "E-ASSIGNEE")
REPORTER = os.getenv("STB_E2E_REPORTER", "E-REVIEWER")
REVIEWER = os.getenv("STB_E2E_REVIEWER", "E-REVIEWER")


def request_json(
    path: str,
    method: str = "GET",
    body: dict | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
):
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        f"{BASE_URL}{path}", data=payload, method=method, headers=request_headers
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode("utf-8")
            return response.status, json.loads(data) if data else None
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {text[:600]}") from exc


def main() -> int:
    status, login = request_json(
        "/api/v1/auth/prototype-login", "POST", {"employee_no": CREATOR}
    )
    assert status == 200
    token = login["access_token"]

    now = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0)
    payload = {
        "task_name": "E2E-AI追问非硬门槛",
        "task_description": "验证AI仍有提示时，完整任务字段可以正常确认发送。",
        "task_goal": "真实HTTP链路进入待接受状态",
        "task_source": None,
        "main_assignee_employee_no": ASSIGNEE,
        "report_to_employee_no": REPORTER,
        "reviewer_employee_no": REVIEWER,
        "start_time": now.isoformat(),
        "deadline": (now + timedelta(days=2)).isoformat(),
        "task_weight": 3,
        "report_cycle": "每周",
        "participants": [],
        "extraction_record_ids": [],
    }
    status, created = request_json("/api/v1/tasks", "POST", payload, token)
    assert status == 201, created
    task_id = created["task_id"]
    version = created["task_version"]
    assert created["status"] == "draft"

    status, submitted = request_json(
        f"/api/v1/tasks/{task_id}/actions/submit-for-confirmation",
        "POST",
        {"expected_task_version": version},
        token,
    )
    assert status == 200, submitted
    assert submitted["status"] in {"pending_confirmation", "pending_confirm"}

    status, sent = request_json(
        f"/api/v1/tasks/{task_id}/actions/confirm-and-send",
        "POST",
        {"expected_task_version": submitted["task_version"]},
        token,
        {"Idempotency-Key": f"e2e-no-clarification-{task_id}-{submitted['task_version']}"},
    )
    assert status == 200, sent
    assert sent["status"] in {"pending_acceptance", "pending_accept"}, sent

    status, detail = request_json(f"/api/v1/tasks/{task_id}", token=token)
    assert status == 200
    assert detail["task_id"] == task_id
    assert detail["task_source"] is None
    assert detail["status"] in {"pending_acceptance", "pending_accept"}
    assert not detail.get("nodes"), "creator send must not generate nodes"

    print("AI_SEND_REAL_HTTP_E2E_PASS")
    print(f"task_id={task_id}")
    print(f"status={detail['status']}")
    print("task_source=null")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - standalone verification utility
        print(f"AI_SEND_REAL_HTTP_E2E_FAIL: {exc}", file=sys.stderr)
        raise
