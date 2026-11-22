from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Content, Title


class DocumentCreate(BaseModel):
    title: Title
    content: Content
    user_id: int


class DocumentTitleUpdate(BaseModel):
    title: Title


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    created_by: int


class DocumentDetailResponse(DocumentResponse):
    latest_version: int | None
    version_count: int


class DocumentCreateResponse(BaseModel):
    document_id: int
    version: int


class DocumentVersionCreate(BaseModel):
    content: Content
    user_id: int


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
