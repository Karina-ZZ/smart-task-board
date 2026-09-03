"""V1.1 PostgreSQL integration-test setup helpers."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import Task, TaskNode
from app.services.features.task_decomposition import TaskDecompositionService

def complete_v11_decomposition(
    factory: sessionmaker[Session], task_id: UUID, assignee_employee_no: str,
    *, keep_active_nodes: int = 2, clock=None,
) -> tuple[tuple[UUID, ...], int]:
    """Run the real V1.1 decomposition transaction for legacy PG fixtures.

    Production requires 5-10 AI nodes. Tests focused on downstream behavior may
    pre-satisfy support nodes after the real decomposition transaction.
    """
    kwargs = {"clock": clock} if clock is not None else {}
    service = TaskDecompositionService(lambda: UnitOfWork(factory), **kwargs)
    record = service.get_latest(task_id, assignee_employee_no)
    with factory() as session:
        task = session.get(Task, task_id)
        assert task is not None and task.start_time is not None and task.deadline is not None
        start, deadline = task.start_time.isoformat(), task.deadline.isoformat()
    result = {
        "nodes": [
            {
                "client_node_id": f"node-{i}",
                "node_name": "Prepare" if i == 1 else "Deliver" if i == 2 else f"Support {i}",
                "action_detail": f"Execute integration step {i}",
                "owner_employee_no": assignee_employee_no,
                "planned_start_time": start,
                "planned_deadline": deadline,
                "deliverable": f"Integration deliverable {i}",
                "acceptance_criteria": f"Integration step {i} accepted",
            }
            for i in range(1, 6)
        ],
        "dependencies": [{
            "predecessor_client_node_id": "node-1",
            "successor_client_node_id": "node-2",
            "dependency_type": "finish_to_start",
        }],
    }
    service.complete_result(task_id, record.decomposition_id, assignee_employee_no, result)
    with factory.begin() as session:
        task = session.get(Task, task_id)
        assert task is not None
        nodes = list(session.query(TaskNode).filter(TaskNode.task_id == task_id).order_by(TaskNode.node_order.asc()))
        assert len(nodes) == 5
        for node in nodes[keep_active_nodes:]:
            node.status = "completed"
            node.progress_percent = 100
            node.completed_at = task.effective_at
        return tuple(node.node_id for node in nodes), task.task_version
