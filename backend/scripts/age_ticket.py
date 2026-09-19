"""Backdate a ticket so age escalation can be demonstrated on command.

    python -m scripts.age_ticket KMC-05-000006 9
    python -m scripts.age_ticket KMC-05-000006 9 --restore

Waiting seven real days to show that a neglected ticket climbs the priority
ladder is not a demo. This moves `created_at` back, runs the sweep, and prints
what moved. `--restore` puts `created_at` back to now.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.category import Category
from app.models.ticket import Ticket
from app.services.ticket_service import apply_priority, sweep_escalations


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    restore = "--restore" in sys.argv

    if not args:
        print(__doc__)
        return 2

    public_code = args[0]
    days = int(args[1]) if len(args) > 1 else 10

    session = get_session_factory()()
    try:
        ticket = session.scalar(
            select(Ticket).where(Ticket.public_code == public_code)
        )
        if ticket is None:
            print(f"No ticket with code {public_code}.")
            return 1

        print(f"{ticket.public_code}  status={ticket.status.value}")
        print(f"  before: priority={ticket.priority.value} "
              f"locked={ticket.priority_locked} created={ticket.created_at:%Y-%m-%d}")

        if ticket.priority_locked:
            print("  NOTE: priority is locked by hand, so the ladder will skip it.")

        ticket.created_at = (
            datetime.now(UTC) if restore else datetime.now(UTC) - timedelta(days=days)
        )
        session.flush()

        # The sweep only looks at tickets old enough to be eligible, so a
        # restored ticket falls outside it. Recompute this one directly.
        category = session.get(Category, ticket.category_id)
        if category is not None:
            apply_priority(ticket, category)

        moved = sweep_escalations(session, force=True)
        session.commit()
        session.refresh(ticket)

        print(f"  after:  priority={ticket.priority.value} "
              f"created={ticket.created_at:%Y-%m-%d}")
        print(f"  sweep moved {moved} ticket(s)")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
