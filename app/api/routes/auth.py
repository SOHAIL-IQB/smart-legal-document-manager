import logging

from fastapi import APIRouter, Request, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import log_event
from app.core.security import create_access_token, login_rate_limiter
from app.db.models import User
from app.schemas.user import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


def _start_session(response: Response, user: User) -> AuthResponse:
    settings = get_settings()
    token = create_access_token(user.id)
    max_age = settings.access_token_minutes * 60
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return AuthResponse(
        user=UserResponse.model_validate(user), access_token=token, expires_in=max_age
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: DbSession) -> AuthResponse:
    user = user_service.register_user(
        db, name=payload.name, email=payload.email, password=payload.password
    )
    return _start_session(response, user)


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

    retry_after = login_rate_limiter.retry_after(key)
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
        log_event("login_failed", logging.WARNING, reason="invalid_credentials")
        raise
    login_rate_limiter.reset(key)
    return _start_session(response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user
