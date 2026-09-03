"""
Feature: WeCom Mini Program authentication.
Responsibilities: map a verified WeCom member to an existing employee,
and issue the existing app session.
Does not own: user provisioning, role assignment, department synchronization, or task authorization.
Plan task: DEV-18 / WeCom authentication baseline.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.wecom import WeComClient, WeComUpstreamError
from app.repositories import UserRepository
from app.services.authentication import AuthenticationService
from app.services.errors import (
    AuthenticationFailedError,
    ExternalIdentityUnavailableError,
    IdentityBindingRequiredError,
)
from app.services.identity import IdentityService


class WeComAuthenticationService:
    """Authenticate through WeCom without changing Smart Task Board business identity semantics."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        wecom_client: WeComClient,
    ) -> None:
        self.session = session
        self.settings = settings
        self.wecom_client = wecom_client
        self._users = UserRepository(session)
        self._sessions = AuthenticationService(session, settings)
        self._identity = IdentityService(session)

    def login(self, code: str, *, user_agent: str | None = None) -> dict[str, object]:
        if self.settings.auth_mode != "wecom":
            raise AuthenticationFailedError("WeCom authentication is not enabled")
        try:
            external_identity = self.wecom_client.code_to_session(code)
        except WeComUpstreamError as exc:
            # Invalid or expired login codes are authentication failures.
            # Provider/infrastructure failures surface as 503.
            if exc.errcode is not None:
                raise AuthenticationFailedError("WeCom login failed") from exc
            raise ExternalIdentityUnavailableError("WeCom identity service is unavailable") from exc

        if external_identity.corp_id != self.settings.wecom_corp_id:
            raise AuthenticationFailedError("WeCom login failed")

        user = self._users.get_by_wecom_user_id_with_department(external_identity.user_id)
        if user is None or user.status != "active":
            raise IdentityBindingRequiredError(
                "当前企业微信账号尚未绑定可用的旺序员工资料，"
                "请联系管理员"
            )

        tokens = self._sessions.issue(user.employee_no, user_agent=user_agent)
        return {
            **tokens,
            "current_user": {
                **self._identity.current_user_context(user.employee_no),
                "auth_mode": self.settings.auth_mode,
            },
        }
