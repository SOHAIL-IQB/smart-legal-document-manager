from fastapi import APIRouter, status

from app.api.deps import DbSession, OwnerAccess, ViewerAccess
from app.db.models import DocumentMember, Role, User
from app.schemas.common import MessageResponse
from app.schemas.member import MemberAdd, MemberResponse, MemberUpdate
from app.services import members as member_service

router = APIRouter(prefix="/documents/{document_id}/members", tags=["sharing"])


def _to_response(member: DocumentMember, user: User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        role=Role(member.role),
        added_at=member.added_at,
    )


@router.get("", response_model=list[MemberResponse])
def list_members(access: ViewerAccess, db: DbSession) -> list[MemberResponse]:
    return [_to_response(m, u) for m, u in member_service.list_members(db, access.document.id)]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(payload: MemberAdd, access: OwnerAccess, db: DbSession) -> MemberResponse:
    return _to_response(
        *member_service.add_member(db, access, email=payload.email, role=payload.role)
    )


@router.patch("/{user_id}", response_model=MemberResponse)
def change_role(
    user_id: int, payload: MemberUpdate, access: OwnerAccess, db: DbSession
) -> MemberResponse:
    return _to_response(*member_service.change_role(db, access, user_id=user_id, role=payload.role))


@router.delete("/{user_id}", response_model=MessageResponse)
def remove_member(user_id: int, access: ViewerAccess, db: DbSession) -> MessageResponse:
    """Owners can remove anyone. Any member can remove themselves to leave the document."""
    member_service.remove_member(db, access, user_id=user_id)
    return MessageResponse(message="Member removed.")
