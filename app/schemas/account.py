"""Account export and deletion (Phase 7 T15)."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.db.models import NotificationKind, Role, VersionSource


class DeleteAccountRequest(BaseModel):
    password: Annotated[str, Field(min_length=1, max_length=128)] = Field(
        description="Your current password, asked again so that a stolen session alone "
        "can't delete the account."
    )


class ExportProfile(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime


class ExportMembership(BaseModel):
    document_id: int
    title: str
    role: Role
    added_at: datetime


class ExportVersion(BaseModel):
    document_id: int
    document_title: str
    version_number: int
    created_at: datetime
    source: VersionSource
    source_filename: str | None
    change_note: str | None
    deleted_at: datetime | None
    content: str


class ExportActivity(BaseModel):
    document_id: int
    action: str
    details: dict[str, Any]
    created_at: datetime


class ExportNotification(BaseModel):
    kind: NotificationKind
    message: str
    document_id: int | None
    version_number: int | None
    created_at: datetime
    read_at: datetime | None


class AccountExport(BaseModel):
    """Your data, limited to documents you can still access."""

    format_version: int
    exported_at: datetime
    profile: ExportProfile
    memberships: list[ExportMembership]
    versions_authored: list[ExportVersion]
    activity: list[ExportActivity]
    notifications: list[ExportNotification]
