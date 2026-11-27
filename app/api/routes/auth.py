import logging

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, DbSession, OptionalUser
from app.api.sessions import end_session, start_session
from app.core.config import get_settings
from app.core.errors import AppError, PermissionDeniedError, RateLimitedError
from app.core.logging import log_event
from app.core.security import login_rate_limiter, verify_password
from app.db.models import User, utcnow
from app.schemas.account import AccountExport, DeleteAccountRequest
from app.schemas.user import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    SessionResponse,
    UserResponse,
)
from app.services import account as account_service
from app.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: DbSession) -> AuthResponse:
    user = user_service.register_user(
        db, name=payload.name, email=payload.email, password=payload.password
    )
    return start_session(response, user)


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={401: {"description": "Wrong email or password"}, 429: {"description": "Too many"}},
)
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> AuthResponse:
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}|{payload.email.lower()}"
    ip_key = f"ip|{client_ip}"

    retry_after = login_rate_limiter.retry_after(key) or login_rate_limiter.retry_after(
        ip_key, get_settings().login_max_failures_per_ip
    )
    if retry_after is not None:
        log_event("login_rate_limited", logging.WARNING, retry_after=retry_after)
        raise RateLimitedError(
            f"Too many failed sign-in attempts. Try again in {retry_after} seconds.",
            details={"retry_after": retry_after},
        )
    try:
        user = user_service.authenticate(db, email=payload.email, password=payload.password)
    except AppError:
        login_rate_limiter.record_failure(key)
        login_rate_limiter.record_failure(ip_key)
        log_event("login_failed", logging.WARNING, reason="invalid_credentials")
        raise
    login_rate_limiter.reset(key)  # not ip_key: a success elsewhere mustn't clear spraying
    return start_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    return end_session(response)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@router.get("/session", response_model=SessionResponse)
def session(user: OptionalUser) -> SessionResponse:
    """Who is signed in, if anyone. Signed out is an answer here, not an error, so a browser's
    first check on each visit doesn't log a failed request. /me keeps answering 401."""
    return SessionResponse(user=UserResponse.model_validate(user) if user else None)


@router.get(
    "/me/export",
    response_model=AccountExport,
    responses={200: {"description": "Sent as a JSON file download"}},
)
def export_me(user: CurrentUser, response: Response, db: DbSession) -> dict[str, object]:
    filename = f"sldm-export-{user.id}-{utcnow().date().isoformat()}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return account_service.export_account(db, user)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Wrong password"},
        409: {"description": "Last owner of documents other members still use"},
        429: {"description": "Too many wrong passwords"},
    },
)
def delete_me(
    payload: DeleteAccountRequest, user: CurrentUser, response: Response, db: DbSession
) -> Response:
    key = f"delete-account|{user.id}"  # same limiter as sign-in, its own key per account
    retry_after = login_rate_limiter.retry_after(key)
    if retry_after is not None:
        log_event("account_delete_rate_limited", logging.WARNING, retry_after=retry_after)
        raise RateLimitedError(
            f"Too many wrong passwords. Try again in {retry_after} seconds.",
            details={"retry_after": retry_after},
        )
    if not verify_password(payload.password, user.password_hash):
        login_rate_limiter.record_failure(key)
        log_event("account_delete_refused", logging.WARNING, reason="wrong_password")
        raise PermissionDeniedError("That password is incorrect.")
    login_rate_limiter.reset(key)

    user_id = user.id
    summary = account_service.delete_account(db, user)
    log_event(
        "account_deleted",
        user_id=user_id,
        documents_deleted=summary.documents_deleted,
        documents_left=summary.documents_left,
    )
    return end_session(response)
