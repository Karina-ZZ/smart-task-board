"""V1.1 PostgreSQL integration-test setup helpers."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.unit_of_work import UnitOfWork
from app.models import Task, TaskNode
from app.services.features.task_decomposition import TaskDecompositionService
from app.services.task_workflow import TaskWorkflowService


def send_accept_and_decompose_v11(
    workflow: TaskWorkflowService,
    factory: sessionmaker[Session],
    task: Task,
    creator_employee_no: str,
    assignee_employee_no: str,
    operation_source: str,
    *,
    self_assigned: bool = False,
    keep_active_nodes: int = 2,
    clock=None,
) -> tuple[tuple[UUID, ...], int]:
    """Advance a valid V1.1 draft through send, acceptance, and AI decomposition.

    PostgreSQL integration tests use this helper so downstream scenarios cannot
    accidentally revive the pre-V1.1 shortcut where creators submitted nodes or
    tasks jumped directly into execution.
    """
    task = workflow.submit_for_confirmation(
        task.task_id,
        creator_employee_no,
        task.task_version,
        operation_source,
    )
    if self_assigned:
        task = workflow.confirm_self_assigned(
            task.task_id,
            creator_employee_no,
            task.task_version,
            operation_source,
        )
    else:
        task = workflow.confirm_and_send(
            task.task_id,
            creator_employee_no,
            task.task_version,
            operation_source,
        )
    task = workflow.accept_task(
        task.task_id,
        assignee_employee_no,
        task.task_version,
        operation_source,
    )
    assert task.status == "decomposing"
    return complete_v11_decomposition(
        factory,
        task.task_id,
        assignee_employee_no,
        keep_active_nodes=keep_active_nodes,
        clock=clock,
    )


def complete_v11_decomposition(
    factory: sessionmaker[Session],
    task_id: UUID,
    assignee_employee_no: str,
    *,
    keep_active_nodes: int = 2,
    clock=None,
) -> tuple[tuple[UUID, ...], int]:
    """Run the real V1.1 decomposition transaction for PostgreSQL fixtures.

    Production requires 5-10 AI nodes. Tests focused on downstream behavior may
    pre-satisfy support nodes after the real decomposition transaction.
    """
    kwargs = {"clock": clock} if clock is not None else {}
    service = TaskDecompositionService(lambda: UnitOfWork(factory), **kwargs)
    record = service.get_latest(task_id, assignee_employee_no)
    with factory() as session:
        task = session.get(Task, task_id)
        assert task is not None
        assert task.start_time is not None
        assert task.deadline is not None
        start = task.start_time.isoformat()
        deadline = task.deadline.isoformat()
    result = {
        "nodes": [
            {
                "client_node_id": f"node-{i}",
                "node_name": (
                    "Prepare" if i == 1 else "Deliver" if i == 2 else f"Support {i}"
                ),
                "action_detail": f"Execute integration step {i}",
                "owner_employee_no": assignee_employee_no,
                "planned_start_time": start,
                "planned_deadline": deadline,
                "deliverable": f"Integration deliverable {i}",
                "acceptance_criteria": f"Integration step {i} accepted",
            }
            for i in range(1, 6)
        ],
        "dependencies": [
            {
                "predecessor_client_node_id": "node-1",
                "successor_client_node_id": "node-2",
                "dependency_type": "finish_to_start",
            }
        ],
    }
    service.complete_result(task_id, record.decomposition_id, assignee_employee_no, result)
    with factory.begin() as session:
        task = session.get(Task, task_id)
        assert task is not None
        statement = (
            select(TaskNode)
            .where(TaskNode.task_id == task_id)
            .order_by(TaskNode.node_order.asc())
        )
        nodes = list(session.scalars(statement).all())
        assert len(nodes) == 5
        for node in nodes[keep_active_nodes:]:
            node.status = "completed"
            node.progress_percent = 100
            node.completed_at = task.effective_at
        return tuple(node.node_id for node in nodes), task.task_version
