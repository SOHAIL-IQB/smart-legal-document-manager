"""Private demo workspaces for visitors without an account (Phase 9 F1)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app.api.deps import CSRF_HEADER, CurrentUser, DbSession
from app.api.sessions import start_session
from app.core.config import get_settings
from app.core.errors import PermissionDeniedError, RateLimitedError
from app.core.logging import log_event
from app.core.security import demo_workspace_limiter
from app.schemas.user import AuthResponse
from app.services import demo as demo_service

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoAccount(BaseModel):
    user_id: int
    name: str
    email: str


class DemoWorkspaceInfo(BaseModel):
    id: int
    expires_at: datetime


class DemoWorkspaceResponse(AuthResponse):
    workspace: DemoWorkspaceInfo
    accounts: list[DemoAccount]


class CurrentWorkspaceResponse(BaseModel):
    workspace: DemoWorkspaceInfo
    accounts: list[DemoAccount]


class SwitchRequest(BaseModel):
    user_id: int


@router.post(
    "/workspaces",
    response_model=DemoWorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": f"Missing the {CSRF_HEADER} header"},
        429: {"description": "Too many new workspaces from this address"},
    },
)
def create_workspace(request: Request, response: Response, db: DbSession) -> DemoWorkspaceResponse:
    """Create a private copy of the demo and sign in as its first account (not safe to retry)."""
    # A cross-site form could otherwise sign a visitor into a demo account (login CSRF).
    if not request.headers.get(CSRF_HEADER):
        raise PermissionDeniedError(f"Starting a demo workspace needs the {CSRF_HEADER} header.")

    client_ip = request.client.host if request.client else "unknown"
    key = f"demo|{client_ip}"
    retry_after = demo_workspace_limiter.retry_after(key, get_settings().demo_workspaces_per_ip)
    if retry_after is not None:
        log_event("demo_workspace_rate_limited", logging.WARNING, retry_after=retry_after)
        raise RateLimitedError(
            f"Too many new demo workspaces from this address. Try again in {retry_after} seconds.",
            details={"retry_after": retry_after},
        )
    demo_workspace_limiter.record_failure(key)  # every creation counts toward the hourly limit

    created = demo_service.create_workspace(db)
    log_event("demo_workspace_created", workspace_id=created.workspace.id)
    session = start_session(response, created.accounts[0])
    return DemoWorkspaceResponse(
        **session.model_dump(),
        workspace=DemoWorkspaceInfo(
            id=created.workspace.id, expires_at=created.workspace.expires_at
        ),
        accounts=[DemoAccount(user_id=a.id, name=a.name, email=a.email) for a in created.accounts],
    )


@router.get(
    "/workspaces/current",
    response_model=CurrentWorkspaceResponse,
    responses={404: {"description": "Not a demo account"}},
)
def current_workspace(user: CurrentUser, db: DbSession) -> CurrentWorkspaceResponse:
    """The signed-in demo account's workspace and its people, so the app can offer the switch."""
    current = demo_service.current_workspace(db, user)
    return CurrentWorkspaceResponse(
        workspace=DemoWorkspaceInfo(
            id=current.workspace.id, expires_at=current.workspace.expires_at
        ),
        accounts=[DemoAccount(user_id=a.id, name=a.name, email=a.email) for a in current.accounts],
    )


@router.post(
    "/workspaces/current/switch",
    response_model=AuthResponse,
    responses={
        403: {"description": "Not a demo account"},
        404: {"description": "Not an account of this workspace"},
    },
)
def switch_account(
    payload: SwitchRequest, user: CurrentUser, response: Response, db: DbSession
) -> AuthResponse:
    """Become another account of the same demo workspace, to see its role."""
    return start_session(response, demo_service.switch_account(db, user, payload.user_id))
