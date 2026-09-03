from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Settings
from app.integrations.wecom import WeComClient, WeComSessionIdentity, WeComUpstreamError


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "auth_mode": "wecom",
        "allow_test_employee_header": False,
        "jwt_secret_key": "app-session-secret-with-at-least-32-characters",
        "wecom_corp_id": "ww-corp-001",
        "wecom_app_secret": "wecom-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_code_to_session_uses_server_side_token_and_returns_only_identity() -> None:
    calls: list[str] = []

    def fake_get(url: str, _timeout: float) -> dict[str, object]:
        calls.append(url)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.path.endswith("/gettoken"):
            assert query["corpid"] == ["ww-corp-001"]
            assert query["corpsecret"] == ["wecom-secret"]
            return {"errcode": 0, "access_token": "ACCESS-1", "expires_in": 7200}
        assert parsed.path.endswith("/miniprogram/jscode2session")
        assert query["access_token"] == ["ACCESS-1"]
        assert query["js_code"] == ["WECOM-CODE"]
        return {
            "errcode": 0,
            "userid": "zhangsan",
            "corpid": "ww-corp-001",
            "session_key": "must-not-escape-client",
        }

    client = WeComClient(_settings(), json_get=fake_get)
    result = client.code_to_session("WECOM-CODE")

    assert result == WeComSessionIdentity(user_id="zhangsan", corp_id="ww-corp-001")
    assert len(calls) == 2
    assert "session_key" not in result.__dict__


def test_access_token_is_cached_across_multiple_login_codes() -> None:
    token_calls = 0

    def fake_get(url: str, _timeout: float) -> dict[str, object]:
        nonlocal token_calls
        if "/gettoken?" in url:
            token_calls += 1
            return {"errcode": 0, "access_token": "ACCESS-CACHED", "expires_in": 7200}
        return {"errcode": 0, "userid": "zhangsan", "corpid": "ww-corp-001"}

    client = WeComClient(_settings(), json_get=fake_get)
    client.code_to_session("CODE-1")
    client.code_to_session("CODE-2")

    assert token_calls == 1


def test_invalid_access_token_is_refreshed_once_before_code_exchange_retries() -> None:
    token_calls = 0
    session_calls = 0

    def fake_get(url: str, _timeout: float) -> dict[str, object]:
        nonlocal token_calls, session_calls
        if "/gettoken?" in url:
            token_calls += 1
            return {"errcode": 0, "access_token": f"ACCESS-{token_calls}", "expires_in": 7200}
        session_calls += 1
        if session_calls == 1:
            return {"errcode": 42001, "errmsg": "access_token expired"}
        return {"errcode": 0, "userid": "zhangsan", "corpid": "ww-corp-001"}

    result = WeComClient(_settings(), json_get=fake_get).code_to_session("CODE-1")

    assert result.user_id == "zhangsan"
    assert token_calls == 2
    assert session_calls == 2


def test_rejected_login_code_is_sanitized_as_upstream_error() -> None:
    def fake_get(url: str, _timeout: float) -> dict[str, object]:
        if "/gettoken?" in url:
            return {"errcode": 0, "access_token": "ACCESS", "expires_in": 7200}
        return {"errcode": 40029, "errmsg": "invalid code containing provider details"}

    with pytest.raises(WeComUpstreamError) as exc_info:
        WeComClient(_settings(), json_get=fake_get).code_to_session("BAD-CODE")

    assert exc_info.value.errcode == 40029
    assert "provider details" not in str(exc_info.value)
