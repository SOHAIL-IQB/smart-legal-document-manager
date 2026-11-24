from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.schemas.common import NoNul

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255), NoNul]
# Upper bound stops very long inputs from wasting CPU in Argon2.
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    name: Name
    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str = Field(description="Also set as an httpOnly cookie for browsers.")
    token_type: str = "bearer"  # noqa: S105 (OAuth token type, not a secret)
    expires_in: int = Field(description="Token lifetime in seconds.")
