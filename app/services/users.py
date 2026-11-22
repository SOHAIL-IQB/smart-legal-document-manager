from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.models import User


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} was not found.")
    return user


def create_user(db: Session, *, name: str, email: str) -> User:
    email = email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise ConflictError(f"A user with email {email} already exists.")

    user = User(name=name, email=email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # two requests raced past the check above
        db.rollback()
        raise ConflictError(f"A user with email {email} already exists.") from exc
    return user


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id.asc())))
