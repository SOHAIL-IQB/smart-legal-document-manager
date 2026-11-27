"""Password hashing, JWT access tokens, and the login rate limiter. See docs/adr/0001."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_ALGORITHM = "HS256"
_password_hash = PasswordHash.recommended()  # Argon2id

# Verified when the email is unknown, so a failed login takes the same time either way.
_DUMMY_HASH = _password_hash.hash("timing-equalizer-not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:  # malformed or unusable stored hash
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a valid token, or None for any invalid/expired token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[_ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "access":
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


class LoginRateLimiter:
    """Counts events (failed logins, new demo workspaces) per key in a sliding window.
    In-memory: one process only (ADR 0001)."""

    def __init__(self, window_seconds: Callable[[], int] | None = None) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._window = window_seconds or (lambda: get_settings().login_window_seconds)

    def _prune(self, key: str, now: float) -> deque[float]:
        window = self._window()
        attempts = self._failures[key]
        while attempts and attempts[0] <= now - window:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str, max_failures: int | None = None) -> int | None:
        """Seconds until the key may try again, or None if it isn't blocked."""
        settings = get_settings()
        limit = settings.login_max_failures if max_failures is None else max_failures
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if not attempts:
                del self._failures[key]  # don't keep an entry for every key ever seen
                return None
            if len(attempts) < limit:
                return None
            return max(1, int(attempts[0] + self._window() - now))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


login_rate_limiter = LoginRateLimiter()
# New demo workspaces per client IP per hour (Phase 9 F1), so nobody can fill the database.
demo_workspace_limiter = LoginRateLimiter(window_seconds=lambda: 3600)
