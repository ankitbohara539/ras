from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, Boolean, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import (
    AlertSeverity,
    AlertTargetType,
    EmergencyType,
    ServiceType,
    SosStatus,
)


class SosRequest(UUIDPrimaryKey, Timestamped, Base):
    """A one-tap emergency request.

    Deliberately not a Ticket: an SOS has its own short lifecycle, is never
    deduplicated, and must never be buried under a parent.
    """

    __tablename__ = "sos_requests"
    __table_args__ = (Index("ix_sos_ward_status", "ward_id", "status"),)

    citizen_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emergency_type: Mapped[EmergencyType] = mapped_column(
        SAEnum(EmergencyType, name="emergency_type", native_enum=True),
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    address_text: Mapped[str | None] = mapped_column(String(300))

    ward_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wards.id", ondelete="SET NULL"),
        index=True,
    )
    municipality_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="SET NULL"),
        index=True,
    )

    note: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(32))

    status: Mapped[SosStatus] = mapped_column(
        SAEnum(SosStatus, name="sos_status", native_enum=True),
        nullable=False,
        default=SosStatus.OPEN,
        index=True,
    )
    acknowledged_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)


class Alert(UUIDPrimaryKey, Timestamped, Base):
    """An area-targeted public safety alert published by an authority.

    Targeting is either a list of wards or a circle. Both are supported
    because "all of ward 5" and "500m around this fire" are different needs.
    """

    __tablename__ = "alerts"

    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
        index=True,
    )
    municipality_id: Mapped[UUID] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title_en: Mapped[str] = mapped_column(String(200), nullable=False)
    title_ne: Mapped[str | None] = mapped_column(String(200))
    body_en: Mapped[str] = mapped_column(Text, nullable=False)
    body_ne: Mapped[str | None] = mapped_column(Text)
    instructions_en: Mapped[str | None] = mapped_column(Text)
    instructions_ne: Mapped[str | None] = mapped_column(Text)

    severity: Mapped[AlertSeverity] = mapped_column(
        SAEnum(AlertSeverity, name="alert_severity", native_enum=True),
        nullable=False,
        default=AlertSeverity.INFO,
        index=True,
    )

    target_type: Mapped[AlertTargetType] = mapped_column(
        SAEnum(AlertTargetType, name="alert_target_type", native_enum=True),
        nullable=False,
    )
    # Populated when target_type is WARD.
    ward_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PGUUID(as_uuid=True)))
    # Populated when target_type is RADIUS.
    center_lat: Mapped[float | None] = mapped_column(Float)
    center_lon: Mapped[float | None] = mapped_column(Float)
    radius_m: Mapped[int | None] = mapped_column(Integer)

    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CivicService(UUIDPrimaryKey, Timestamped, Base):
    """A hospital, police post, ward office, shelter and so on."""

    __tablename__ = "civic_services"
    __table_args__ = (Index("ix_service_type_ward", "service_type", "ward_id"),)

    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ne: Mapped[str | None] = mapped_column(String(200))
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, name="service_type", native_enum=True),
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(String(32))
    alt_phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(300))

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    ward_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wards.id", ondelete="SET NULL"),
        index=True,
    )
    municipality_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="SET NULL"),
        index=True,
    )

    is_24x7: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes_en: Mapped[str | None] = mapped_column(Text)
    notes_ne: Mapped[str | None] = mapped_column(Text)
