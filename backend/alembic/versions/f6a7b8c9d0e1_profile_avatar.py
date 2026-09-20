"""profile avatar storage path

Revision ID: f6a7b8c9d0e1
Revises: e4f7a05c26d3
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e4f7a05c26d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("avatar_path", sa.String(length=400), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "avatar_path")
