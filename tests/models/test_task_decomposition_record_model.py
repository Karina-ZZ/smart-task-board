from sqlalchemy import CheckConstraint, DateTime, Integer, String, Uuid, inspect
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Task, TaskDecompositionRecord


def test_decomposition_record_columns_constraints_and_relationship() -> None:
    table = TaskDecompositionRecord.__table__
    assert table.name == "task_decomposition_records"
    assert set(table.columns.keys()) == {
        "decomposition_id", "task_id", "triggered_by_employee_no", "trigger_type",
        "input_snapshot", "status", "task_version", "idempotency_key", "model_name",
        "model_version", "prompt_version", "node_count", "result_json", "error_code",
        "error_message", "retry_count", "started_at", "completed_at", "created_at",
    }
    assert isinstance(table.c.decomposition_id.type, Uuid)
    assert isinstance(table.c.input_snapshot.type, JSONB)
    assert isinstance(table.c.result_json.type, JSONB)
    assert isinstance(table.c.status.type, String)
    assert isinstance(table.c.task_version.type, Integer)
    for field in ("started_at", "completed_at", "created_at"):
        assert isinstance(table.c[field].type, DateTime)
        assert table.c[field].type.timezone is True
    checks = {c.name: str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
    assert "pending" in checks["ck_task_decomposition_records_status"]
    assert "invalidated" in checks["ck_task_decomposition_records_status"]
    assert next(iter(table.c.task_id.foreign_keys)).target_fullname == "tasks.task_id"
    assert (
        inspect(TaskDecompositionRecord).relationships.task.back_populates
        == "decomposition_records"
    )
    assert inspect(Task).relationships.decomposition_records.back_populates == "task"


def test_decomposition_record_has_idempotency_and_one_active_partial_unique_indexes() -> None:
    indexes = {index.name: index for index in TaskDecompositionRecord.__table__.indexes}
    assert indexes["uq_task_decomposition_records_idempotency"].unique is True
    active = indexes["uq_task_decomposition_records_one_active"]
    assert active.unique is True
    where = str(active.dialect_options["postgresql"]["where"])
    assert "pending" in where and "running" in where
