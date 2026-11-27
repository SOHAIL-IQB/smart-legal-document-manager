"""Starting and ending a browser session: the token goes in an httpOnly cookie for browsers and
in the response body for API clients (ADR 0001). Shared by the auth and demo routes."""

from fastapi import Response, status

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.models import User
from app.schemas.user import AuthResponse, UserResponse


def start_session(response: Response, user: User) -> AuthResponse:
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


def end_session(response: Response) -> Response:
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
