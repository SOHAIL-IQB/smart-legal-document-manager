from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(UserResponse):
    pass


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    user_id: int


class DocumentTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class DocumentVersionCreate(BaseModel):
    content: str = Field(..., min_length=1)
    user_id: int


class DocumentVersionResponse(BaseModel):
    id: int
    version_number: int
    content: str
    edited_by: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    created_by: int

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(DocumentResponse):
    latest_version: int | None
    version_count: int


class DocumentCreateResponse(BaseModel):
    document_id: int
    version: int


class DocumentVersionCreateResponse(BaseModel):
    message: str
    document_id: int
    version: int | None = None


class CompareResponse(BaseModel):
    document_id: int
    version_1: int
    version_2: int
    before: str
    after: str
    changes: list[str]
    has_meaningful_changes: bool


class DeleteResponse(BaseModel):
    message: str
