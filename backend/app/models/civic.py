"""Civic-sense complaints: a citizen reporting another *person's* conduct.

Littering, dumping, spitting, blocking the footpath -- the problem is an
act, not a broken thing, so it is not a ticket: nobody repairs it, nobody
merges duplicates of it, and above all it is never public. The photo shows a
real, identifiable person, so these are visible only to the citizen who filed
one, the ward office where it happened, and administrators.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CivicCategory, CivicStatus
from app.models.geography import Municipality, Ward


class CivicComplaint(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "civic_complaints"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_civic_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_civic_lon"),
        Index("ix_civic_ward_status", "ward_id", "status"),
    )

    # CIV-KMC-08-000001: quotable, and distinct from ticket codes at a glance.
    public_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)

    reporter_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[CivicCategory] = mapped_column(
        SAEnum(CivicCategory, name="civic_category", native_enum=True), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address_text: Mapped[str | None] = mapped_column(String(300))
    ward_id: Mapped[UUID] = mapped_column(
        ForeignKey("wards.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    municipality_id: Mapped[UUID] = mapped_column(
        ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # When it happened, which is not when it was reported: people file from
    # home in the evening about what they saw that morning.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[CivicStatus] = mapped_column(
        SAEnum(CivicStatus, name="civic_status", native_enum=True),
        nullable=False,
        default=CivicStatus.SUBMITTED,
        index=True,
    )
    # What the office did ("Warned the shop owner", "Fined Rs 500") or why
    # it was dismissed. Shown to the reporter.
    action_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ward: Mapped["Ward"] = relationship(lazy="joined")
    municipality: Mapped["Municipality"] = relationship(lazy="joined")
    photos: Mapped[list["CivicComplaintPhoto"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="CivicComplaintPhoto.created_at",
    )

    @property
    def ward_number(self) -> int | None:
        return self.ward.number if self.ward else None

    @property
    def ward_name(self) -> str | None:
        return self.ward.name_en if self.ward else None


class CivicComplaintPhoto(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "civic_complaint_photos"

    complaint_id: Mapped[UUID] = mapped_column(
        ForeignKey("civic_complaints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)

    complaint: Mapped["CivicComplaint"] = relationship(back_populates="photos")
