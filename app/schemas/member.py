from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.db.models import Role


class MemberAdd(BaseModel):
    email: EmailStr
    role: Role = Role.VIEWER


class MemberUpdate(BaseModel):
    role: Role


class MemberResponse(BaseModel):
    user_id: int
    name: str
    email: EmailStr
    role: Role
    added_at: datetime
