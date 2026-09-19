"""Re-read every existing comment for urgency and re-score the tickets.

Comments posted before urgency detection existed were stored with
is_urgent = false. Run this once after `alembic upgrade head` (and again if
the phrase list in app/ml/urgency.py changes):

    python -m scripts.backfill_urgency            # apply
    python -m scripts.backfill_urgency --dry-run  # report only
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.session import get_session_factory
from app.ml.urgency import is_urgent
from app.models.ticket import Ticket, TicketComment
from app.services.ticket_service import refresh_comment_urgency


def main(dry_run: bool) -> None:
    db = get_session_factory()()
    try:
        flagged = 0
        touched: set = set()
        for comment in db.scalars(select(TicketComment)).all():
            urgent = is_urgent(comment.body)
            if urgent != comment.is_urgent:
                comment.is_urgent = urgent
                touched.add(comment.ticket_id)
            flagged += urgent

        # Re-score every ticket with comments, not only the changed ones, so
        # the count is right even if it was edited by hand.
        ticket_ids = set(db.scalars(select(TicketComment.ticket_id).distinct()).all())
        moved = 0
        for ticket in db.scalars(select(Ticket).where(Ticket.id.in_(ticket_ids))).all():
            before = (ticket.urgent_commenter_count, ticket.priority)
            refresh_comment_urgency(db, ticket)
            after = (ticket.urgent_commenter_count, ticket.priority)
            if before != after:
                moved += 1
                print(
                    f"{ticket.public_code}: urgent commenters {before[0]} -> {after[0]}, "
                    f"priority {before[1].value} -> {after[1].value}"
                )

        print(
            f"{flagged} urgent comment(s); {len(touched)} ticket(s) had comments "
            f"re-flagged; {moved} ticket(s) changed."
        )
        if dry_run:
            db.rollback()
            print("Dry run: nothing saved.")
        else:
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
