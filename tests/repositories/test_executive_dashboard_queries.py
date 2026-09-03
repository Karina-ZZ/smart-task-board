"""Feature 15 PostgreSQL SQL-contract tests for executive employee task filtering."""
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.repositories.executive_dashboard import ExecutiveDashboardRepository


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"render_postcompile": True},
        )
    )


def test_employee_task_scope_query_filters_department_and_main_assignee() -> None:
    session = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    session.scalars.return_value = scalars
    repository = ExecutiveDashboardRepository(session)
    department_id = uuid4()

    assert repository.list_tasks_for_scope({department_id}, "E-1001") == []

    statement = session.scalars.call_args.args[0]
    sql = _sql(statement)
    assert "tasks.department_id IN" in sql
    assert "tasks.main_assignee_employee_no" in sql
    assert "ORDER BY tasks.created_at, tasks.task_id" in sql
    assert "E-1001" not in sql, "employee filter must remain parameterized"
