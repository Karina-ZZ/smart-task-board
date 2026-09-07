"""
Feature: Enterprise WeCom self-built-application message provider.
Responsibilities: resolve an internal employee number to the bound WeCom userid
and deliver the existing notification copy through the self-built app.
Does not own: reminder generation, outbox retries, task permissions, or employee provisioning.
H5 migration: V1.
"""

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.wecom.client import WeComClient, WeComUpstreamError
from app.models import User


class WeComApplicationMessageProvider:
    """Production delivery adapter used only when AUTH_MODE=wecom."""

    def __init__(self, session: Session, settings: Settings, client: WeComClient) -> None:
        self.session = session
        self.settings = settings
        self.client = client

    def send(self, recipient_employee_no: str, title: str, content: str) -> str:
        user = self.session.get(User, recipient_employee_no)
        wecom_user_id = (user.wecom_user_id if user is not None else None) or ""
        if not wecom_user_id.strip():
            raise WeComUpstreamError("recipient employee is not bound to a WeCom userid")
        base = self.settings.wecom_h5_base_url.strip().rstrip("/")
        return self.client.send_application_message(
            wecom_user_id,
            title,
            content,
            web_url=f"{base}/notifications" if base else None,
        )
