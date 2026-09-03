#!/usr/bin/env python3
"""Minimal real-WeCom identity smoke test without printing tokens or secrets.

Obtain a fresh code from ``wx.qy.login`` in the real mini program, then run this
script against a deployed FastAPI instance configured with AUTH_MODE=wecom.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    bearer: str | None = None,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = {"detail": raw[:500]}
        return exc.code, data
    except URLError as exc:
        raise SystemExit(f"network error: {exc.reason}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"REAL WECOM E2E FAIL: {message}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("WANGXU_E2E_API_BASE_URL", ""),
        help="Deployed FastAPI base URL, for example https://api.example.com",
    )
    parser.add_argument(
        "--code",
        default=os.getenv("WECOM_TEST_LOGIN_CODE", ""),
        help="Fresh one-time code returned by wx.qy.login",
    )
    parser.add_argument(
        "--employee-no",
        default=os.getenv("WECOM_TEST_EXPECTED_EMPLOYEE_NO", ""),
        help="Expected existing users.employee_no for the WeCom account",
    )
    parser.add_argument(
        "--role-type",
        default=os.getenv("WECOM_TEST_EXPECTED_ROLE_TYPE", ""),
        help="Optional expected local role_type, e.g. employee or executive",
    )
    args = parser.parse_args()

    _require(bool(args.api_base_url), "--api-base-url is required")
    _require(bool(args.code), "--code is required; obtain a fresh wx.qy.login code")
    _require(bool(args.employee_no), "--employee-no is required")

    status, live = _request(args.api_base_url, "/health/live")
    _require(status == 200 and live == {"status": "ok"}, f"/health/live returned {status}")
    status, ready = _request(args.api_base_url, "/health/ready")
    _require(
        status == 200 and ready == {"status": "ready"},
        f"/health/ready returned {status}; PostgreSQL must be ready",
    )

    status, login = _request(
        args.api_base_url,
        "/api/v1/auth/wecom",
        method="POST",
        payload={"code": args.code},
    )
    _require(status == 200 and isinstance(login, dict), f"WeCom login returned {status}")
    current_user = login.get("current_user") or {}
    _require(
        current_user.get("employee_no") == args.employee_no,
        "WeCom userid did not map to the expected local employee_no",
    )
    _require(current_user.get("auth_mode") == "wecom", "auth_mode is not wecom")
    if args.role_type:
        _require(current_user.get("role_type") == args.role_type, "role_type mismatch")

    access_token = login.get("access_token")
    refresh_token = login.get("refresh_token")
    _require(bool(access_token and refresh_token), "login response is missing session tokens")

    status, me = _request(
        args.api_base_url,
        "/api/v1/me",
        bearer=access_token,
    )
    _require(status == 200, f"/api/v1/me returned {status}")
    _require(me.get("employee_no") == args.employee_no, "/me identity changed after login")
    _require(
        "permissions" in me and "roles" in me and "scopes" in me,
        "/me permission projection missing",
    )

    status, ai_token = _request(
        args.api_base_url,
        "/api/v1/auth/ai-token",
        method="POST",
        bearer=access_token,
    )
    _require(status == 200 and bool(ai_token.get("token")), f"AI token returned {status}")

    status, rotated = _request(
        args.api_base_url,
        "/api/v1/auth/refresh",
        method="POST",
        payload={"refresh_token": refresh_token},
    )
    _require(status == 200, f"refresh returned {status}")
    rotated_access = rotated.get("access_token")
    rotated_refresh = rotated.get("refresh_token")
    _require(
        bool(rotated_access and rotated_refresh),
        "refresh rotation did not return both tokens",
    )

    status, me_after_refresh = _request(
        args.api_base_url,
        "/api/v1/me",
        bearer=rotated_access,
    )
    _require(status == 200, f"/me after refresh returned {status}")
    _require(
        me_after_refresh.get("employee_no") == args.employee_no,
        "identity changed after refresh rotation",
    )

    status, _ = _request(
        args.api_base_url,
        "/api/v1/auth/logout",
        method="POST",
        bearer=rotated_access,
    )
    _require(status == 204, f"logout returned {status}")

    status, _ = _request(
        args.api_base_url,
        "/api/v1/auth/refresh",
        method="POST",
        payload={"refresh_token": rotated_refresh},
    )
    _require(status in {401, 403}, "refresh token still works after logout")

    print("REAL_WECOM_IDENTITY_E2E_PASS")
    print(f"employee_no={args.employee_no}")
    if args.role_type:
        print(f"role_type={args.role_type}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
