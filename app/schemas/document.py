from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.models import Role, VersionSource
from app.schemas.common import Content, NoNul, Title
from app.utils.diff import DiffRow, DiffStats

ChangeNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500), NoNul]


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
    created_by_name: str
    my_role: Role
    latest_version: int | None = Field(description="Newest version that isn't deleted.")
    version_count: int = Field(description="Number of versions that aren't deleted.")
    word_count: int | None = Field(description="Words in the latest version.")


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


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
    source_filename: str | None
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
    version_1_meta: DocumentVersionSummary
    version_2_meta: DocumentVersionSummary
    has_meaningful_changes: bool
    stats: DiffStats
    rows: list[DiffRow] = Field(description="Side-by-side rows with word-level segments.")
    before: str
    after: str
    changes: list[str] = Field(description="Unified diff lines, kept for API clients.")
