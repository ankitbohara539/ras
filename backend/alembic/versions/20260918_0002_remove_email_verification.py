"""Remove account email verification and activate pending users.

Revision ID: 20260918_0002
Revises: 20260918_0001
"""

from alembic import op
import sqlalchemy as sa

revision = "20260918_0002"
down_revision = "20260918_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Accounts that were waiting for an email become usable immediately.
    op.execute(
        "UPDATE users SET status = 'ACTIVE' WHERE status = 'PENDING_VERIFICATION'"
    )
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        """
        CREATE TABLE email_verification_tokens (
          id CHAR(36) PRIMARY KEY,
          user_id CHAR(36) NOT NULL,
          token_hash CHAR(64) NOT NULL UNIQUE,
          expires_at DATETIME(6) NOT NULL,
          used_at DATETIME(6),
          created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
          INDEX ix_verify_user (user_id),
          INDEX ix_verify_expires (expires_at),
          CONSTRAINT fk_verify_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
