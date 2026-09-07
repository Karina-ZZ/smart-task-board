"""Test14 F2/F3: AI intake and direct internal commands share the DB format.

Session doubles exercise boundaries only; real persistence has a separate PG test.
"""
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.report_cycle import REPORT_CYCLE_RE, is_valid_report_cycle
from app.models import AIExtractionRecord, Task, TaskInput
from app.services import business_capabilities as business_module
from app.services.business_capabilities import TaskIntakeService
from app.services.commands import CreateTaskDraftCommand
from app.services.errors import BusinessValidationError
from app.services.task_workflow import TaskWorkflowService
from tests.services.test_business_capabilities import NOW, RecordingSession


@pytest.mark.parametrize("raw", ["weekly", "\u6bcf\u5468", "weekly:MON@24:00", 3, True])
def test_internal_create_rejects_invalid_cycle_before_entering_uow(raw):
    factory = MagicMock()
    with pytest.raises(BusinessValidationError, match="report_cycle"):
        TaskWorkflowService(factory).create_task_draft(CreateTaskDraftCommand(
            task_name="Test14", creator_employee_no="CREATOR", operation_source="test14",
            report_cycle=raw,
        ))
    factory.assert_not_called()


@pytest.mark.parametrize("raw", ["weekly", "\u6bcf\u5468", "weekly:XXX@09:00", 42])
def test_ai_invalid_cycle_is_advisory_null_and_never_required(raw):
    service = TaskIntakeService(RecordingSession(), MagicMock())
    result = service._validated_extraction_result({
        "extracted_json": {"task_name": "Test14", "report_cycle": raw},
        "missing_fields": ["report_cycle"], "low_confidence_fields": [],
    })
    assert result["extracted_json"]["report_cycle"] is None
    assert "report_cycle" in result["low_confidence_fields"]
    assert "report_cycle" not in result["missing_fields"]


@pytest.mark.parametrize("raw", [None, "weekly:MON@00:00", "weekly:SAT@23:59"])
def test_ai_valid_or_empty_cycle_is_unchanged(raw):
    service = TaskIntakeService(RecordingSession(), MagicMock())
    result = service._validated_extraction_result({
        "extracted_json": {"task_name": "Test14", "report_cycle": raw},
    })
    assert result["extracted_json"]["report_cycle"] == raw
    assert "report_cycle" not in result["missing_fields"]
    assert "report_cycle" not in result["low_confidence_fields"]


@pytest.mark.parametrize("correction", [{}, {"reportCycle": "weekly:FRI@17:00"},
                                      {"report_cycle": None}])
def test_legacy_invalid_ai_cycle_cannot_override_explicit_correction(monkeypatch, correction):
    input_id, extraction_id = uuid4(), uuid4()
    extraction = AIExtractionRecord(
        extraction_id=extraction_id, input_id=input_id,
        extracted_json={
            "task_name": "Test14", "task_description": "Description",
            "task_goal": "Goal", "main_assignee_employee_no": "ASSIGNEE",
            "report_to_employee_no": "REVIEWER", "reviewer_employee_no": "REVIEWER",
            "deadline": "2026-09-10T18:00:00+08:00", "task_weight": 3,
            "acceptance_criteria": "Done", "report_cycle": "weekly",
        }, missing_fields=[], low_confidence_fields=[], confirm_questions=[],
    )
    session = RecordingSession(objects={
        (TaskInput, input_id): TaskInput(input_id=input_id, submitted_by_employee_no="CREATOR"),
        (AIExtractionRecord, extraction_id): extraction,
    })
    captured = []

    class CapturingWorkflow:
        def __init__(self, _factory, **kwargs):
            pass

        def create_task_draft(self, command):
            captured.append(command)
            return Task(task_id=command.task_id)

    monkeypatch.setattr(business_module, "TaskWorkflowService", CapturingWorkflow)
    TaskIntakeService(session, MagicMock(), clock=lambda: NOW).create_draft_from_extraction(
        "CREATOR", extraction_id=extraction_id, corrections=correction,
    )
    expected = correction.get("reportCycle", correction.get("report_cycle"))
    assert captured[0].report_cycle == expected
    assert extraction.extracted_json["report_cycle"] == "weekly"  # historical evidence unchanged


def test_prompts_and_existing_database_constraint_match_format_contract():
    checks = [str(c.sqltext) for c in Task.__table__.constraints if hasattr(c, "sqltext")]
    assert any(REPORT_CYCLE_RE.pattern in value for value in checks)
    root = Path(__file__).resolve().parents[2]
    legacy = (root / "app/ai/prompts/task_agent.md").read_text()
    assert '"reportCycle": "weekly"' not in legacy
    for relative in ["app/ai/prompts/task_intake.md",
                     "cloud-functions/ChatService/prompts/task_intake.md"]:
        prompt = (root / relative).read_text()
        assert "weekly:MON@09:00" in prompt
        assert '"reportCycle": null' in prompt
    assert is_valid_report_cycle("weekly:MON@09:00")
