"""Feature 06 creator-flow people DTOs."""
from uuid import UUID
from app.schemas.common import DecimalString, StrictSchema
class TaskCreationPersonResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None
    department_name: str | None
    position: str | None
    org_level: str | None
    workload_score: DecimalString | None
    workload_level: str | None
