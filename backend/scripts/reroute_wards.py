"""Re-route existing tickets to the ward they are actually in.

Tickets filed before ward routing used OpenStreetMap were placed by the
nearest *generated* ward centroid, which was usually the wrong ward and
sometimes the wrong municipality. This recomputes each one with the current
rule (ticket_service.resolve_ward).

Moving a ticket changes which ward office can see it, so this only reports
by default:

    python -m scripts.reroute_wards           # show what would move
    python -m scripts.reroute_wards --apply   # move them

The public code (KMC-07-000006) is kept: people have already quoted it.
Nominatim allows one lookup a second, so this takes about a second a ticket.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.ticket import Ticket, TicketStatusHistory
from app.services.ticket_service import resolve_ward


def main(apply: bool) -> None:
    db = get_session_factory()()
    try:
        tickets = db.scalars(select(Ticket).order_by(Ticket.created_at)).all()
        moves = 0
        for ticket in tickets:
            target = resolve_ward(db, ticket.latitude, ticket.longitude)
            if target.id == ticket.ward_id:
                continue

            before = f"{ticket.municipality_code}-{ticket.ward_number:02d}"
            after = f"{target.municipality.code}-{target.number:02d}"
            print(f"{ticket.public_code}: ward {before} -> {after}  ({ticket.title[:40]})")
            moves += 1

            if apply:
                ticket.ward = target
                ticket.ward_id = target.id
                ticket.municipality_id = target.municipality_id
                db.add(
                    TicketStatusHistory(
                        ticket_id=ticket.id,
                        from_status=ticket.status,
                        to_status=ticket.status,
                        changed_by_id=None,
                        note=f"Re-routed from ward {before} to {after} (real ward boundaries)",
                    )
                )

        print(f"{moves} of {len(tickets)} ticket(s) {'moved' if apply else 'would move'}.")
        if apply:
            db.commit()
        else:
            db.rollback()
            print("Dry run: nothing saved. Re-run with --apply to move them.")
    finally:
        db.close()


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
