from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.models import User, UserAuthorizedScope
from app.repositories import UserRepository
from app.services.errors import EntityNotFoundError, PermissionDeniedError

PROTOTYPE_WARNING = "Prototype authentication is for isolated demo use only."
EXECUTIVE_ROUTE_ROLES = {"admin", "executive"}
MANAGE_PERMISSION_ROLES = {"admin"}


class IdentityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._users = UserRepository(session)

    @staticmethod
    def _require_prototype_enabled(settings: Settings) -> None:
        if settings.auth_mode != "prototype" or not settings.prototype_auth_enabled:
            raise EntityNotFoundError("prototype authentication is unavailable")

    def list_prototype_users(self, settings: Settings) -> list[User]:
        self._require_prototype_enabled(settings)
        users = self._users.list_by_employee_nos(settings.prototype_employee_nos)
        by_employee_no = {user.employee_no: user for user in users if user.status == "active"}
        return [
            by_employee_no[employee_no]
            for employee_no in settings.prototype_employee_nos
            if employee_no in by_employee_no
        ]

    def prototype_login(self, employee_no: str, settings: Settings) -> tuple[User, str, int]:
        self._require_prototype_enabled(settings)
        if employee_no not in settings.prototype_employee_nos:
            raise PermissionDeniedError("prototype login failed")
        user = self._users.get_by_employee_no_with_department(employee_no)
        if user is None or user.status != "active":
            raise PermissionDeniedError("prototype login failed")
        token, expires_in = create_access_token(employee_no, settings)
        return user, token, expires_in

    def get_active_user(self, employee_no: str) -> User:
        user = self._users.get_by_employee_no_with_department(employee_no)
        if user is None or user.status != "active":
            raise PermissionDeniedError("current identity is unavailable")
        return user

    def list_active_scopes(self, employee_no: str) -> list[UserAuthorizedScope]:
        now = datetime.now(UTC)
        statement = (
            select(UserAuthorizedScope)
            .where(
                UserAuthorizedScope.employee_no == employee_no,
                UserAuthorizedScope.status == "active",
                or_(
                    UserAuthorizedScope.valid_from.is_(None),
                    UserAuthorizedScope.valid_from <= now,
                ),
                or_(
                    UserAuthorizedScope.valid_to.is_(None),
                    UserAuthorizedScope.valid_to >= now,
                ),
            )
            .order_by(UserAuthorizedScope.scope_type, UserAuthorizedScope.scope_id)
        )
        return list(self.session.scalars(statement).all())

    def current_user_context(self, employee_no: str) -> dict[str, object]:
        user = self.get_active_user(employee_no)
        scopes = self.list_active_scopes(employee_no)
        department = None
        if user.department is not None:
            department = {
                "department_id": user.department.department_id,
                "department_name": user.department.department_name,
            }
        return {
            "employee_no": user.employee_no,
            "name": user.name,
            "department": department,
            "role_type": user.role_type,
            "roles": [user.role_type],
            "permissions": self.current_user_permissions(user, scopes),
            "scopes": [
                {
                    "authorized_scope_id": scope.authorized_scope_id,
                    "scope_type": scope.scope_type,
                    "scope_id": scope.scope_id,
                    "permission_type": scope.permission_type,
                }
                for scope in scopes
            ],
        }

    def current_user_permissions(
        self, user: User, scopes: list[UserAuthorizedScope]
    ) -> dict[str, object]:
        # FR-22: system role and authorized scope are separate gates.
        # Employees never gain the executive board merely from a scope row.
        # P0: administrators read all tasks by default, while executive/team
        # dashboard access remains a separate projected capability.
        scoped_team_access = any(
            scope.permission_type in {"view", "manage", "export"}
            and scope.scope_type in {"all_demo_data", "department", "user", "role"}
            for scope in scopes
        )
        can_access_executive = user.role_type == "executive" or (
            user.role_type == "admin" and scoped_team_access
        )
        can_view_all_demo_data = user.role_type in EXECUTIVE_ROUTE_ROLES and any(
            scope.scope_type == "all_demo_data"
            and scope.permission_type in {"view", "manage", "export"}
            for scope in scopes
        )

        can_view_all_tasks = user.role_type == "admin"
        capabilities = ["task:read:related"]
        if can_view_all_tasks:
            capabilities.append("task:read:all")
        allowed_routes = [
            "/workbench",
            "/tasks",
            "/task/:taskId",
            "/task/:taskId/report",
            "/task/:taskId/review",
            "/task/:taskId/decomposition",
            "/create/details",
            "/create/confirm",
            "/notifications",
            "/profile",
        ]
        if can_access_executive:
            capabilities.append("executive:read")
            allowed_routes.extend(["/executive", "/executive/employee-tasks"])
        if user.role_type in MANAGE_PERMISSION_ROLES:
            capabilities.append("permissions:manage")

        return {
            "can_access_executive": can_access_executive,
            "can_manage_permissions": user.role_type in MANAGE_PERMISSION_ROLES,
            "can_view_all_tasks": can_view_all_tasks,
            "can_view_all_demo_data": can_view_all_demo_data,
            "allowed_routes": allowed_routes,
            "capabilities": capabilities,
        }
