"""
Feature: WeCom identity integration.
Responsibilities: expose the WeCom API client used by authentication.
Does not own: business authorization, task permissions, or session persistence.
Plan task: DEV-18 / WeCom authentication baseline.
"""

from app.integrations.wecom.client import WeComClient, WeComSessionIdentity, WeComUpstreamError

__all__ = ["WeComClient", "WeComSessionIdentity", "WeComUpstreamError"]
