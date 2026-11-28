"""Private demo workspaces (Phase 9 F1; spec D2 in docs/specs/phase-8-design-direction.md).

Each visitor gets their own three accounts and the four sample contracts, so they can do anything,
including share, restore and delete, without changing what the next visitor sees. Workspaces are
isolated from each other and from real accounts:
- `members.add_member` refuses to share across them;
- `users.authenticate` refuses demo accounts;
- `deps.get_current_user` refuses an expired workspace's sessions.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.db.models import DemoWorkspace, Document, Notification, User, utcnow
from app.services import sample_data

DEMO_PEOPLE = ("Asha Rao", "Ben Carter", "Chloe Martin")


@dataclass(frozen=True)
class CreatedWorkspace:
    workspace: DemoWorkspace
    accounts: list[User]  # in DEMO_PEOPLE order; the visitor starts as the first


def create_workspace(db: Session) -> CreatedWorkspace:
    purge_expired(db)
    now = utcnow()
    workspace = DemoWorkspace(
        created_at=now, expires_at=now + timedelta(hours=get_settings().demo_workspace_hours)
    )
    db.add(workspace)
    db.flush()  # assigns workspace.id for the account emails

    tag = f"w{workspace.id}-{secrets.token_hex(3)}"
    # A hash of a random secret nobody keeps: demo accounts can never sign in with a password.
    unusable = hash_password(secrets.token_urlsafe(32))
    accounts = [
        User(
            name=name,
            email=f"{name.split()[0].lower()}.{tag}@demo.example",
            password_hash=unusable,
            demo_workspace_id=workspace.id,
        )
        for name in DEMO_PEOPLE
    ]
    db.add_all(accounts)
    db.commit()
    sample_data.populate(db, *accounts)
    return CreatedWorkspace(workspace=workspace, accounts=accounts)


def current_workspace(db: Session, user: User) -> CreatedWorkspace:
    """The signed-in demo account's workspace and its people, in the order they were created."""
    workspace = db.get(DemoWorkspace, user.demo_workspace_id) if user.demo_workspace_id else None
    if workspace is None:
        raise NotFoundError("You are not in a demo workspace.")
    accounts = db.scalars(
        select(User)
        .where(User.demo_workspace_id == workspace.id, User.deleted_at.is_(None))
        .order_by(User.id)
    ).all()
    return CreatedWorkspace(workspace=workspace, accounts=list(accounts))


def switch_account(db: Session, current: User, target_id: int) -> User:
    """Another account of the same workspace, so the visitor can see each role."""
    if current.demo_workspace_id is None:
        raise PermissionDeniedError("Only demo accounts can switch to another account.")
    target = db.get(User, target_id)
    same_workspace = target is not None and target.demo_workspace_id == current.demo_workspace_id
    if not same_workspace or target is None or target.deleted_at is not None:
        raise NotFoundError(f"Account {target_id} is not in this demo workspace.")
    return target


def purge_expired(db: Session, now: datetime | None = None) -> int:
    """Delete expired workspaces and everything in them. Returns how many were removed."""
    cutoff = now or utcnow()
    expired = list(db.scalars(select(DemoWorkspace.id).where(DemoWorkspace.expires_at <= cutoff)))
    if not expired:
        return 0
    accounts = select(User.id).where(User.demo_workspace_id.in_(expired))

    # Their documents (members, versions and activity go with them in the database). Isolation
    # guarantees no real account is a member of these, or wrote anything in them.
    for document in db.scalars(select(Document).where(Document.created_by.in_(accounts))):
        db.delete(document)
    db.flush()
    db.execute(
        delete(Notification).where(
            or_(Notification.user_id.in_(accounts), Notification.actor_id.in_(accounts))
        )
    )
    db.execute(delete(User).where(User.demo_workspace_id.in_(expired)))
    db.execute(delete(DemoWorkspace).where(DemoWorkspace.id.in_(expired)))
    db.commit()
    return len(expired)
