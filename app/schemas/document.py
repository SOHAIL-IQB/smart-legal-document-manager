from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db.models import Role, VersionSource
from app.schemas.common import Content, Title

ChangeNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


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
    change_note: ChangeNote | None = None


class RestoreRequest(BaseModel):
    change_note: ChangeNote | None = None


class DocumentVersionSummary(BaseModel):
    """A version without its content, for history lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    edited_by: int
    edited_by_name: str
    created_at: datetime
    change_note: str | None
    source: VersionSource
    restored_from: int | None
    word_count: int
    content_hash: str
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: int | None


class DocumentVersionResponse(DocumentVersionSummary):
    content: str


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
