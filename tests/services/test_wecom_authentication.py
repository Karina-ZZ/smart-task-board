from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.integrations.wecom import WeComSessionIdentity, WeComUpstreamError
from app.services.errors import (
    AuthenticationFailedError,
    ExternalIdentityUnavailableError,
    IdentityBindingRequiredError,
)
from app.services.wecom_authentication import WeComAuthenticationService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://test:test@localhost/test",
        "auth_mode": "wecom",
        "allow_test_employee_header": False,
        "jwt_secret_key": "app-session-secret-with-at-least-32-characters",
        "wecom_corp_id": "ww-corp-001",
        "wecom_agent_id": "1000002",
        "wecom_app_secret": "wecom-secret",
    }
    values.update(overrides)
    return Settings(**values)


def _service() -> tuple[WeComAuthenticationService, MagicMock]:
    client = MagicMock()
    service = WeComAuthenticationService(MagicMock(), _settings(), client)
    service._users = MagicMock()
    service._sessions = MagicMock()
    service._identity = MagicMock()
    return service, client


def test_verified_wecom_user_maps_to_existing_employee_and_reuses_session_service() -> None:
    service, client = _service()
    client.code_to_session.return_value = WeComSessionIdentity(
        user_id="zhangsan",
        corp_id="ww-corp-001",
    )
    service._users.get_by_wecom_user_id_with_department.return_value = SimpleNamespace(
        employee_no="E001",
        status="active",
    )
    service._sessions.issue.return_value = {
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 1800,
    }
    service._identity.current_user_context.return_value = {
        "employee_no": "E001",
        "name": "张三",
        "department": None,
        "role_type": "employee",
        "roles": ["employee"],
        "permissions": {},
        "scopes": [],
    }

    result = service.login("CODE", user_agent="mini-program")

    service._users.get_by_wecom_user_id_with_department.assert_called_once_with("zhangsan")
    service._sessions.issue.assert_called_once_with("E001", user_agent="mini-program")
    assert result["current_user"]["employee_no"] == "E001"
    assert result["current_user"]["auth_mode"] == "wecom"


def test_foreign_corp_is_rejected_before_local_user_lookup() -> None:
    service, client = _service()
    client.code_to_session.return_value = WeComSessionIdentity(
        user_id="zhangsan",
        corp_id="ww-other-corp",
    )

    with pytest.raises(AuthenticationFailedError, match="WeCom login failed"):
        service.login("CODE")

    service._users.get_by_wecom_user_id_with_department.assert_not_called()


@pytest.mark.parametrize("user", [None, SimpleNamespace(employee_no="E001", status="disabled")])
def test_unbound_or_disabled_member_cannot_create_local_identity(user: object) -> None:
    service, client = _service()
    client.code_to_session.return_value = WeComSessionIdentity(
        user_id="zhangsan",
        corp_id="ww-corp-001",
    )
    service._users.get_by_wecom_user_id_with_department.return_value = user

    with pytest.raises(IdentityBindingRequiredError):
        service.login("CODE")

    service._sessions.issue.assert_not_called()


def test_wecom_code_rejection_is_401_but_transport_failure_is_503() -> None:
    service, client = _service()
    client.code_to_session.side_effect = WeComUpstreamError("rejected", errcode=40029)
    with pytest.raises(AuthenticationFailedError):
        service.login("BAD")

    client.code_to_session.side_effect = WeComUpstreamError("network")
    with pytest.raises(ExternalIdentityUnavailableError):
        service.login("CODE")
