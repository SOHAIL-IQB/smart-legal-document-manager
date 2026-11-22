from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import Role
from app.schemas.common import Content, Title


class DocumentCreate(BaseModel):
    title: Title
    content: Content


class DocumentTitleUpdate(BaseModel):
    title: Title


class DocumentResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    created_by: int
    my_role: Role


class DocumentDetailResponse(DocumentResponse):
    latest_version: int | None
    version_count: int


class DocumentCreateResponse(BaseModel):
    document_id: int
    version: int


class DocumentVersionCreate(BaseModel):
    content: Content


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    content: str
    edited_by: int
    created_at: datetime


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
