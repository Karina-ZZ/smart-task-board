"""
Feature: Deterministic performance-metric matching.

Responsibilities:
- Export reproducible task-to-KPI scoring helpers for DEV-14.
- Keep LLM providers out of performance-match decisions.

Does not own: HTTP parsing, task authorization, persistence, or user confirmation.
Plan task: DEV-14.
"""

from .scoring import MatchScore, PerformanceMatchScorer

__all__ = ["MatchScore", "PerformanceMatchScorer"]
