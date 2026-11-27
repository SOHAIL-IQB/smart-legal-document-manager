"""Demo data for a portfolio walkthrough (Phase 7 T10).

    python -m scripts.seed

Creates 3 demo users and 4 sample contracts (app/services/sample_data.py, shared with the private
demo workspaces) through the real services, so version history, the activity log and notifications
look exactly like real use. Safe to re-run (it stops if the demo users exist) and refuses to run
when ENVIRONMENT=production.

All contract text is original sample text written for this demo, not legal advice.
"""

import sys
from dataclasses import dataclass

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services import sample_data
from app.services.users import find_user_by_email, register_user

DEMO_PASSWORD = "demo password 2026"  # noqa: S105  [W4]


@dataclass(frozen=True)
class DemoUser:
    name: str
    email: str


DEMO_USERS = (
    DemoUser("Asha Rao", "asha@demo.example"),
    DemoUser("Ben Carter", "ben@demo.example"),
    DemoUser("Chloe Martin", "chloe@demo.example"),
)


def run() -> bool:
    """Seed the demo data. Returns False when it was already there."""
    if get_settings().environment == "production":
        raise SystemExit("Refusing to seed demo data when ENVIRONMENT=production.")

    with SessionLocal() as db:
        if find_user_by_email(db, DEMO_USERS[0].email) is not None:
            return False
        asha, ben, chloe = (
            register_user(db, name=u.name, email=u.email, password=DEMO_PASSWORD)
            for u in DEMO_USERS
        )
        sample_data.populate(db, asha, ben, chloe)
    return True


def main() -> None:
    created = run()
    if created:
        print("Demo data created. Sign in with any of:")
        for user in DEMO_USERS:
            print(f"  {user.email}  (password: {DEMO_PASSWORD})")
    else:
        print("Demo data already present; nothing changed.")


if __name__ == "__main__":
    sys.exit(main())
