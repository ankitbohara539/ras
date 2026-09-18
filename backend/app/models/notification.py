from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import NotificationType


class Notification(UUIDPrimaryKey, Timestamped, Base):
    """An in-app notification.

    When a parent ticket resolves, every child reporter gets one of these --
    that fan-out is the payoff for merging duplicates in the first place.
    """

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_unread", "user_id", "read_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type", native_enum=True),
        nullable=False,
    )

    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ne: Mapped[str | None] = mapped_column(String(200))
    body_en: Mapped[str | None] = mapped_column(Text)
    body_ne: Mapped[str | None] = mapped_column(Text)

    ticket_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
    )
    alert_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"),
    )
    sos_request_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sos_requests.id", ondelete="CASCADE"),
    )

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
