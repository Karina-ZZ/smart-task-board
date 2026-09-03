"""Public entry for the DEV-16 executive dashboard feature."""

from app.services.features.executive_dashboard.periods import PeriodWindow, resolve_executive_period
from app.services.features.executive_dashboard.service import ExecutiveDashboardService

__all__ = ["ExecutiveDashboardService", "PeriodWindow", "resolve_executive_period"]
