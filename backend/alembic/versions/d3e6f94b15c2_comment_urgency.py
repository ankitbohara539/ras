"""comment urgency

Comments that press for a faster fix are flagged, and each ticket keeps a
count of distinct citizens who wrote one, which feeds its priority.

Revision ID: d3e6f94b15c2
Revises: c2d5e83a04b1
Create Date: 2026-09-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e6f94b15c2"
down_revision: Union[str, None] = "c2d5e83a04b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_comments",
        sa.Column("is_urgent", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "urgent_commenter_count", sa.Integer(), server_default="0", nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("tickets", "urgent_commenter_count")
    op.drop_column("ticket_comments", "is_urgent")
