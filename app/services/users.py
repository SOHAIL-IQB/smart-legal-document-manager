from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AuthenticationError, ConflictError
from app.core.security import hash_password, verify_password
from app.db.models import User

INVALID_CREDENTIALS = "Incorrect email or password."


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def register_user(db: Session, *, name: str, email: str, password: str) -> User:
    email = email.lower()
    if find_user_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists.")

    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # two requests raced past the check above
        db.rollback()
        raise ConflictError("An account with this email already exists.") from exc
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = find_user_by_email(db, email)
    # verify_password runs a dummy hash when user is None, so timing doesn't reveal the email.
    if not verify_password(password, user.password_hash if user else None) or user is None:
        raise AuthenticationError(INVALID_CREDENTIALS)
    return user
