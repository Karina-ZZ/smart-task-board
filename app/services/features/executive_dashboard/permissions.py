"""
Feature: Executive dashboard department authorization.
Responsibilities: resolve explicit department/view scopes and expand active descendants.
Does not own: dashboard metrics, task visibility writes, or HTTP responses.
Plan task: DEV-16.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models import Department
from app.repositories.executive_dashboard import ExecutiveDashboardRepository
from app.services.errors import PermissionDeniedError


@dataclass(frozen=True)
class ExecutiveScope:
    root_department_ids: frozenset[UUID]
    authorized_department_ids: frozenset[UUID]
    department_ids: frozenset[UUID]
    selected_department_id: UUID | None


class ExecutiveScopeResolver:
    def __init__(self, repo: ExecutiveDashboardRepository) -> None:
        self.repo = repo

    def authorize(
        self, actor: str, requested_department_id: UUID | None, now: datetime
    ) -> tuple[ExecutiveScope, list[Department]]:
        user = self.repo.get_user(actor)
        if user is None or user.status != "active" or user.role_type not in {"executive", "admin"}:
            self._deny(actor if user else None, requested_department_id, now)
        scopes = self.repo.list_active_department_scopes(actor, now)
        departments = self.repo.list_active_departments()
        by_id = {row.department_id: row for row in departments}
        roots = {
            UUID(row.scope_id)
            for row in scopes
            if row.scope_id and self._is_uuid(row.scope_id)
        }
        roots &= set(by_id)
        authorized = self.expand_departments(roots, departments)
        if not authorized:
            self._deny(actor, requested_department_id, now)
        if requested_department_id is not None and requested_department_id not in authorized:
            self._deny(actor, requested_department_id, now)
        effective = (
            authorized
            if requested_department_id is None
            else self.expand_departments({requested_department_id}, departments) & authorized
        )
        return (
            ExecutiveScope(
                frozenset(roots),
                frozenset(authorized),
                frozenset(effective),
                requested_department_id,
            ),
            departments,
        )

    def authorize_employee(
        self, actor: str, scope: ExecutiveScope, employee_no: str, now: datetime
    ):
        """Require the selected employee to belong to the effective executive department scope."""
        employee = self.repo.get_user(employee_no)
        if (
            employee is None
            or employee.status != "active"
            or employee.department_id is None
            or employee.department_id not in scope.department_ids
        ):
            self._deny(actor, employee.department_id if employee is not None else None, now)
        return employee

    def _deny(self, actor: str | None, department_id: UUID | None, now: datetime) -> None:
        self.repo.add_scope_denied_log(actor, department_id, "SCOPE_DENIED", now)
        raise PermissionDeniedError("SCOPE_DENIED")

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            UUID(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def expand_departments(roots: set[UUID], departments: list[Department]) -> set[UUID]:
        children: dict[UUID | None, list[UUID]] = defaultdict(list)
        for row in departments:
            children[row.parent_department_id].append(row.department_id)
        result = set(roots)
        stack = list(roots)
        while stack:
            parent = stack.pop()
            for child in children.get(parent, []):
                if child not in result:
                    result.add(child)
                    stack.append(child)
        return result

    @staticmethod
    def payload(scope: ExecutiveScope, departments: list[Department]) -> dict[str, object]:
        allowed = set(scope.authorized_department_ids)
        return {
            "selected_department_id": scope.selected_department_id,
            "departments": [
                {
                    "department_id": row.department_id,
                    "department_name": row.department_name,
                    "department_type": row.department_type,
                    "parent_department_id": row.parent_department_id,
                }
                for row in departments
                if row.department_id in allowed
            ],
        }
