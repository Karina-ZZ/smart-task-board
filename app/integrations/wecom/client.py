"""
Feature: WeCom H5 OAuth identity client.
Responsibilities: cache application access tokens and exchange WeCom web OAuth
codes for member identity.
Does not own: employee mapping, authorization, or Smart Task Board session issuance.
Plan task: DEV-18 / WeCom authentication baseline.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import Settings

JsonGet = Callable[[str, float], dict[str, object]]
JsonPost = Callable[[str, dict[str, object], float], dict[str, object]]
TOKEN_INVALID_ERRCODES = {40014, 42001}


class WeComUpstreamError(RuntimeError):
    """Raised when WeCom rejects or cannot complete an identity request."""

    def __init__(self, message: str, *, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


@dataclass(frozen=True)
class WeComSessionIdentity:
    """Identity facts returned by WeCom H5 web OAuth identity exchange."""

    user_id: str
    corp_id: str


@dataclass
class _AccessToken:
    value: str
    expires_at: datetime

    def is_usable(self, now: datetime) -> bool:
        # Keep a small safety window so requests do not race token expiration.
        return self.expires_at > now + timedelta(seconds=60)


def _json_get(url: str, timeout_seconds: float) -> dict[str, object]:
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        # The configured base URL is validated server-side and defaults to WeCom HTTPS.
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # urllib exposes several transport exceptions; sanitize at this boundary.
        raise WeComUpstreamError("WeCom request failed") from exc
    if not isinstance(payload, dict):
        raise WeComUpstreamError("WeCom returned an invalid response")
    return payload


def _json_post(url: str, payload: dict[str, object], timeout_seconds: float) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise WeComUpstreamError("WeCom request failed") from exc
    if not isinstance(result, dict):
        raise WeComUpstreamError("WeCom returned an invalid response")
    return result


class WeComClient:
    """Small synchronous client for access-token and H5 OAuth member-identity exchange."""

    def __init__(
        self,
        settings: Settings,
        *,
        json_get: JsonGet | None = None,
        json_post: JsonPost | None = None,
    ) -> None:
        self.settings = settings
        self._json_get = json_get or _json_get
        self._json_post = json_post or _json_post
        self._access_token: _AccessToken | None = None
        self._token_lock = Lock()

    @property
    def _base_url(self) -> str:
        return self.settings.wecom_api_base_url.rstrip("/")

    def clear_access_token(self) -> None:
        with self._token_lock:
            self._access_token = None

    def _fetch_access_token(self) -> str:
        secret = self.settings.wecom_app_secret
        if secret is None:
            raise WeComUpstreamError("WeCom application secret is not configured")
        query = urlencode(
            {
                "corpid": self.settings.wecom_corp_id,
                "corpsecret": secret.get_secret_value(),
            }
        )
        payload = self._json_get(
            f"{self._base_url}/cgi-bin/gettoken?{query}",
            float(self.settings.wecom_request_timeout_seconds),
        )
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            raise WeComUpstreamError("WeCom access token request was rejected", errcode=errcode)
        token = str(payload.get("access_token") or "").strip()
        expires_in = int(payload.get("expires_in", 0) or 0)
        if not token or expires_in <= 0:
            raise WeComUpstreamError("WeCom access token response was incomplete")
        self._access_token = _AccessToken(
            value=token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        return token

    def access_token(self) -> str:
        now = datetime.now(UTC)
        with self._token_lock:
            if self._access_token is not None and self._access_token.is_usable(now):
                return self._access_token.value
            return self._fetch_access_token()

    def _code_to_session_once(self, code: str, access_token: str) -> dict[str, object]:
        # H5 self-built applications exchange the one-time OAuth code through
        # auth/getuserinfo. The application access token already binds the request
        # to the configured enterprise, so the upstream response does not need to
        # echo corpid like the old Mini Program code2Session response did.
        query = urlencode({"access_token": access_token, "code": code})
        return self._json_get(
            f"{self._base_url}/cgi-bin/auth/getuserinfo?{query}",
            float(self.settings.wecom_request_timeout_seconds),
        )

    def _send_application_message_once(
        self,
        access_token: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        return self._json_post(
            f"{self._base_url}/cgi-bin/message/send?{urlencode({'access_token': access_token})}",
            payload,
            float(self.settings.wecom_request_timeout_seconds),
        )


    def _agent_id(self) -> int | str:
        value = self.settings.wecom_agent_id
        return int(value) if value.isdigit() else value

    def send_application_message(
        self,
        user_id: str,
        title: str,
        content: str,
        *,
        web_url: str | None = None,
    ) -> str:
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise WeComUpstreamError("WeCom recipient userid is empty")
        if web_url:
            message: dict[str, object] = {
                "touser": normalized_user_id,
                "msgtype": "textcard",
                "agentid": self._agent_id(),
                "textcard": {
                    "title": title[:128],
                    "description": content[:2048],
                    "url": web_url,
                    "btntxt": "查看详情",
                },
                "enable_id_trans": 0,
            }
        else:
            message = {
                "touser": normalized_user_id,
                "msgtype": "text",
                "agentid": self._agent_id(),
                "text": {"content": f"{title}\n{content}"[:2048]},
                "enable_id_trans": 0,
            }
        payload = self._send_application_message_once(self.access_token(), message)
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode in TOKEN_INVALID_ERRCODES:
            self.clear_access_token()
            payload = self._send_application_message_once(self.access_token(), message)
            errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            raise WeComUpstreamError("WeCom application message was rejected", errcode=errcode)
        message_id = payload.get("msgid") or payload.get("invaliduser")
        return str(message_id or f"wecom:{normalized_user_id}")

    def code_to_session(self, code: str) -> WeComSessionIdentity:
        normalized_code = code.strip()
        if not normalized_code:
            raise WeComUpstreamError("WeCom login code is empty")
        payload = self._code_to_session_once(normalized_code, self.access_token())
        errcode = int(payload.get("errcode", 0) or 0)
        if errcode in TOKEN_INVALID_ERRCODES:
            self.clear_access_token()
            payload = self._code_to_session_once(normalized_code, self.access_token())
            errcode = int(payload.get("errcode", 0) or 0)
        if errcode != 0:
            raise WeComUpstreamError("WeCom login code was rejected", errcode=errcode)

        user_id = str(payload.get("userid") or "").strip()
        if not user_id:
            raise WeComUpstreamError("WeCom login response did not contain an enterprise member")
        return WeComSessionIdentity(
            user_id=user_id,
            corp_id=self.settings.wecom_corp_id.strip(),
        )
