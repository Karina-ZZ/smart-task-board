"""
Feature: creator-flow people candidates.
Responsibilities: return active employees the actor may assign, enriched with department/latest workload.
Does not own: task mutation or business-action authorization.
Plan task: WECHAT-MP-06 / CR-16.
"""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import User, WorkloadSnapshot
from app.services.business_capabilities import PermissionScopeService
from app.services.errors import PermissionDeniedError

class TaskCreationPeopleService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_candidates(self, actor: str, keyword: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        current = self.session.get(User, actor)
        if current is None or current.status != "active":
            raise PermissionDeniedError("active login is required")
        statement = select(User).where(User.status == "active").options(selectinload(User.department)).order_by(User.name, User.employee_no)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            statement = statement.where(User.name.ilike(pattern) | User.employee_no.ilike(pattern))
        policy = PermissionScopeService(self.session)
        users = [user for user in self.session.scalars(statement.limit(300)).all() if policy.can_assign_employee(actor, user.employee_no)]
        rows=[]
        for user in users:
            snapshot = self.session.scalar(select(WorkloadSnapshot).where(WorkloadSnapshot.employee_no==user.employee_no).order_by(WorkloadSnapshot.calculated_at.desc()).limit(1))
            rows.append({
                "employee_no": user.employee_no, "name": user.name,
                "department_id": user.department_id,
                "department_name": user.department.department_name if user.department else None,
                "position": user.position, "org_level": user.org_level,
                "workload_score": snapshot.workload_score if snapshot else None,
                "workload_level": snapshot.workload_level if snapshot else None,
            })
        rows.sort(key=lambda item: (item["workload_score"] is None, item["workload_score"] or 999, item["name"], item["employee_no"]))
        return rows[:limit]
