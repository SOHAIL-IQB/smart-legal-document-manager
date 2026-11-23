"""Request dependencies: the signed-in user and their access to a document."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.models import Role, User
from app.db.session import get_db
from app.services.documents import DocumentAccess, get_document_access

DbSession = Annotated[Session, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False, description="JWT from /api/auth/login")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-Requested-With"


def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get(get_settings().auth_cookie_name)
        if token and request.method not in _SAFE_METHODS and not request.headers.get(CSRF_HEADER):
            # A cross-site form can carry the cookie but cannot add a custom header.
            raise PermissionDeniedError(
                f"Requests that change data must send the {CSRF_HEADER} header."
            )

    if not token:
        raise AuthenticationError("Not signed in.")
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise AuthenticationError("Your session is invalid or has expired. Please sign in again.")
    request.state.user_id = user.id  # for the access log line
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(minimum: Role) -> Callable[..., DocumentAccess]:
    def dependency(document_id: int, user: CurrentUser, db: DbSession) -> DocumentAccess:
        return get_document_access(db, document_id=document_id, user=user, minimum=minimum)

    return dependency


ViewerAccess = Annotated[DocumentAccess, Depends(require_role(Role.VIEWER))]
EditorAccess = Annotated[DocumentAccess, Depends(require_role(Role.EDITOR))]
OwnerAccess = Annotated[DocumentAccess, Depends(require_role(Role.OWNER))]
