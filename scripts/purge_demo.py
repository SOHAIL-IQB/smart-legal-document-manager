"""Delete expired demo workspaces and everything in them (Phase 9 F1).

    python -m scripts.purge_demo

Run it on a schedule (for example hourly). Creating a new workspace also purges expired ones, so
this only matters when nobody starts a demo for a while.
"""

from app.db.session import SessionLocal
from app.services import demo as demo_service


def main() -> None:
    with SessionLocal() as db:
        removed = demo_service.purge_expired(db)
    print(f"Removed {removed} expired demo workspace{'' if removed == 1 else 's'}.")


if __name__ == "__main__":
    main()
