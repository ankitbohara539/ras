from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import CandidateStatus, Language, TicketPriority, TicketStatus
from app.models.geography import Municipality, Ward

EMBEDDING_DIM = 256


class Ticket(UUIDPrimaryKey, Timestamped, Base):
    """A reported civic issue.

    Tickets form a one-level tree: a ticket with parent_id set is a duplicate
    report folded under a parent. Only an authority may set parent_id -- the
    matcher writes suggestions to DuplicateCandidate and never touches this.
    """

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_ticket_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_ticket_lon"),
        CheckConstraint("id <> parent_id", name="ck_ticket_not_own_parent"),
        # Candidate lookup always filters ward + status, then bounding box.
        Index("ix_ticket_ward_status", "ward_id", "status"),
        Index("ix_ticket_bbox", "latitude", "longitude"),
    )

    public_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"),
        index=True,
    )
    reporter_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_lang: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", native_enum=True, create_type=False),
        nullable=False,
        default=Language.EN,
    )

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address_text: Mapped[str | None] = mapped_column(String(300))

    ward_id: Mapped[UUID] = mapped_column(
        ForeignKey("wards.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    municipality_id: Mapped[UUID] = mapped_column(
        ForeignKey("municipalities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status", native_enum=True),
        nullable=False,
        default=TicketStatus.REPORTED,
        index=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority", native_enum=True),
        nullable=False,
        default=TicketPriority.MEDIUM,
        index=True,
    )

    # Denormalised counters, maintained by the service layer.
    child_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    corroboration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispute_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    community_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Matcher output kept on the ticket itself.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    predicted_category_key: Mapped[str | None] = mapped_column(String(48))
    category_confidence: Mapped[float | None] = mapped_column(Float)

    assigned_to_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        index=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)

    # Eager-loaded: every ticket listing shows which ward owns it, and the
    # alternative is an N+1 across the dashboard.
    ward: Mapped["Ward"] = relationship(lazy="selectin")
    municipality: Mapped["Municipality"] = relationship(lazy="selectin")

    parent: Mapped["Ticket | None"] = relationship(
        remote_side="Ticket.id",
        back_populates="children",
    )
    children: Mapped[list["Ticket"]] = relationship(back_populates="parent")
    photos: Mapped[list["TicketPhoto"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )

    @property
    def ward_number(self) -> int | None:
        return self.ward.number if self.ward else None

    @property
    def ward_name(self) -> str | None:
        return self.ward.name_en if self.ward else None

    @property
    def municipality_code(self) -> str | None:
        return self.municipality.code if self.municipality else None

    @property
    def is_child(self) -> bool:
        return self.parent_id is not None

    @property
    def report_count(self) -> int:
        """Total people who reported this issue: the original plus children."""
        return self.child_count + 1


class TicketPhoto(UUIDPrimaryKey, Timestamped, Base):
    """A photo in Supabase Storage, plus the perceptual hash used for matching."""

    __tablename__ = "ticket_photos"

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(400), nullable=False)
    # 64-bit perceptual hash rendered as 16 hex chars.
    phash: Mapped[str | None] = mapped_column(String(16), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    ticket: Mapped["Ticket"] = relationship(back_populates="photos")


class TicketCorroboration(UUIDPrimaryKey, Timestamped, Base):
    """A nearby citizen confirming (or disputing) that a report is real.

    Only counted when the citizen is physically inside the category match
    radius, one vote per citizen per ticket, and never on your own report.
    """

    __tablename__ = "ticket_corroborations"
    __table_args__ = (
        UniqueConstraint("ticket_id", "citizen_id", name="uq_corroboration_once"),
    )

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citizen_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class DuplicateCandidate(UUIDPrimaryKey, Timestamped, Base):
    """A merge suggestion from the matcher, awaiting authority review.

    This table is the only thing the model writes. Merging is a human action.
    """

    __tablename__ = "duplicate_candidates"
    __table_args__ = (
        UniqueConstraint("ticket_id", "candidate_ticket_id", name="uq_candidate_pair"),
        CheckConstraint(
            "ticket_id <> candidate_ticket_id", name="ck_candidate_not_self"
        ),
    )

    # The newly submitted ticket.
    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The existing ticket it might belong under.
    candidate_ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    category_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    text_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    image_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    geo_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[CandidateStatus] = mapped_column(
        SAEnum(CandidateStatus, name="candidate_status", native_enum=True),
        nullable=False,
        default=CandidateStatus.PENDING,
        index=True,
    )
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketStatusHistory(UUIDPrimaryKey, Timestamped, Base):
    """Append-only audit trail of every status transition."""

    __tablename__ = "ticket_status_history"

    ticket_id: Mapped[UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[TicketStatus | None] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status", native_enum=True, create_type=False),
    )
    to_status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status", native_enum=True, create_type=False),
        nullable=False,
    )
    changed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
    )
    note: Mapped[str | None] = mapped_column(Text)
