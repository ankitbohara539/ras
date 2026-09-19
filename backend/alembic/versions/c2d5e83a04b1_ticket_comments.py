"""ticket comments

Adds the discussion thread on a ticket (visibility mirrors the ticket itself)
and a notification type for it. `ALTER TYPE ... ADD VALUE` cannot run inside
the transaction Alembic wraps migrations in by default, so it is committed
separately before the rest of the migration runs.

Revision ID: c2d5e83a04b1
Revises: b1c4d7e29f10
Create Date: 2026-09-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d5e83a04b1"
down_revision: Union[str, None] = "b1c4d7e29f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'TICKET_COMMENTED'")

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])
    op.create_index("ix_ticket_comments_author_id", "ticket_comments", ["author_id"])

    # Same lockdown as every other table -- RLS on, no policies, so only the
    # service-role backend can read or write it.
    op.execute("ALTER TABLE ticket_comments ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_ticket_comments_author_id", table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_ticket_id", table_name="ticket_comments")
    op.drop_table("ticket_comments")
    # Postgres cannot drop a single enum value; downgrading here would require
    # rebuilding the notification_type enum from scratch. Left as a no-op,
    # matching the accepted stance on additive enum values in this project.
