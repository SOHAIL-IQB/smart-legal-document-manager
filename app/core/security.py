"""Password hashing, JWT access tokens, and the login rate limiter. See docs/adr/0001."""

import threading
import time
from collections import defaultdict, deque
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
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a valid token, or None for any invalid/expired token."""
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
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
    """Counts failed logins per key in a sliding window. In-memory: one process only (ADR 0001)."""

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        window = get_settings().login_window_seconds
        attempts = self._failures[key]
        while attempts and attempts[0] <= now - window:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int | None:
        """Seconds until the key may try again, or None if it isn't blocked."""
        settings = get_settings()
        now = time.monotonic()
        with self._lock:
            attempts = self._prune(key, now)
            if not attempts:
                del self._failures[key]  # don't keep an entry for every key ever seen
                return None
            if len(attempts) < settings.login_max_failures:
                return None
            return max(1, int(attempts[0] + settings.login_window_seconds - now))

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
