"""civic complaints

Citizens reporting another person's conduct (littering, spitting, blocking
the footpath...). Private to the reporter, the ward office and admins.

Revision ID: e4f7a05c26d3
Revises: d3e6f94b15c2
Create Date: 2026-09-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f7a05c26d3"
down_revision: Union[str, None] = "d3e6f94b15c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Stored by member name, like every other enum in this schema.
CATEGORIES = (
    "LITTERING",
    "DUMPING_WASTE",
    "BURNING_WASTE",
    "SPITTING",
    "PUBLIC_URINATION",
    "SMOKING_IN_PUBLIC",
    "NOISE",
    "ILLEGAL_PARKING",
    "FOOTPATH_ENCROACHMENT",
    "VANDALISM",
    "PET_WASTE",
    "OTHER",
)
STATUSES = ("SUBMITTED", "UNDER_REVIEW", "ACTION_TAKEN", "DISMISSED")


def upgrade() -> None:
    # ADD VALUE cannot run inside the migration's transaction.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'CIVIC_COMPLAINT_UPDATED'"
        )

    category = postgresql.ENUM(*CATEGORIES, name="civic_category")
    civic_status = postgresql.ENUM(*STATUSES, name="civic_status")
    category.create(op.get_bind(), checkfirst=True)
    civic_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "civic_complaints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("public_code", sa.String(40), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("category", postgresql.ENUM(name="civic_category", create_type=False), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address_text", sa.String(300)),
        sa.Column("ward_id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", postgresql.ENUM(name="civic_status", create_type=False), nullable=False),
        sa.Column("action_note", sa.Text()),
        sa.Column("reviewed_by_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_civic_lat"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_civic_lon"),
        sa.ForeignKeyConstraint(["reporter_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_code"),
    )
    op.create_index("ix_civic_complaints_reporter_id", "civic_complaints", ["reporter_id"])
    op.create_index("ix_civic_complaints_ward_id", "civic_complaints", ["ward_id"])
    op.create_index("ix_civic_complaints_municipality_id", "civic_complaints", ["municipality_id"])
    op.create_index("ix_civic_complaints_status", "civic_complaints", ["status"])
    op.create_index("ix_civic_ward_status", "civic_complaints", ["ward_id", "status"])

    op.create_table(
        "civic_complaint_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("complaint_id", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.String(400), nullable=False),
        sa.ForeignKeyConstraint(["complaint_id"], ["civic_complaints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_civic_complaint_photos_complaint_id", "civic_complaint_photos", ["complaint_id"]
    )

    # Same lockdown as every other table: RLS on, no policies, so only the
    # service-role backend can read these -- never the browser directly.
    op.execute("ALTER TABLE civic_complaints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE civic_complaint_photos ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("civic_complaint_photos")
    op.drop_table("civic_complaints")
    postgresql.ENUM(name="civic_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="civic_category").drop(op.get_bind(), checkfirst=True)
    # notification_type keeps its added value; see the ticket_comments migration.
