from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from app.schemas.common import StrictSchema
from app.schemas.current_user import CurrentUserResponse

EmployeeNo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PrototypeUserResponse(StrictSchema):
    employee_no: str
    name: str
    department_id: UUID | None
    department_name: str | None
    role_type: str


class PrototypeLoginRequest(StrictSchema):
    employee_no: EmployeeNo


class PrototypeLoginUserResponse(StrictSchema):
    employee_no: str
    name: str


class PrototypeLoginResponse(StrictSchema):
    access_token: str = Field(repr=False)
    token_type: str = "bearer"
    expires_in: int
    user: PrototypeLoginUserResponse


class WeComLoginRequest(StrictSchema):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)]


class AiTokenResponse(StrictSchema):
    token: str = Field(repr=False)
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(StrictSchema):
    refresh_token: EmployeeNo


class TokenResponse(StrictSchema):
    access_token: str = Field(repr=False)
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str = Field(repr=False)


class LoginResponse(TokenResponse):
    current_user: CurrentUserResponse
