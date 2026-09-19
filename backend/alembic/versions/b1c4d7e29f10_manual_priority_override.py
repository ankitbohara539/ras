"""manual priority override

Adds the four columns behind a human-set priority. `priority_locked` is what
automation checks: when it is true, neither the score nor the age ladder will
write to `priority` again until someone clears it.

Revision ID: b1c4d7e29f10
Revises: a5ee60c2664f
Create Date: 2026-09-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4d7e29f10"
down_revision: Union[str, None] = "a5ee60c2664f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "priority_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("priority_set_by_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("priority_set_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("tickets", sa.Column("priority_note", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_tickets_priority_set_by_id_profiles",
        "tickets",
        "profiles",
        ["priority_set_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tickets_priority_set_by_id_profiles", "tickets", type_="foreignkey"
    )
    op.drop_column("tickets", "priority_note")
    op.drop_column("tickets", "priority_set_at")
    op.drop_column("tickets", "priority_set_by_id")
    op.drop_column("tickets", "priority_locked")
