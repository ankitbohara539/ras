
from uuid import UUID

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey
from app.models.enums import MunicipalityType


class Municipality(UUIDPrimaryKey, Timestamped, Base):
    """A nagarpalika. Authority accounts are scoped to one of these."""

    __tablename__ = "municipalities"

    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_ne: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    province: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[MunicipalityType] = mapped_column(
        SAEnum(MunicipalityType, name="municipality_type", native_enum=True),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)

    wards: Mapped[list["Ward"]] = relationship(
        back_populates="municipality",
        cascade="all, delete-orphan",
    )


class Ward(UUIDPrimaryKey, Timestamped, Base):
    """A ward inside a municipality. This is the unit of report isolation."""

    __tablename__ = "wards"
    __table_args__ = (
        UniqueConstraint("municipality_id", "number", name="uq_ward_number"),
    )

    municipality_id: Mapped[UUID] = mapped_column(
        ForeignKey("municipalities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(120))
    name_ne: Mapped[str | None] = mapped_column(String(120))
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, nullable=False)

    municipality: Mapped["Municipality"] = relationship(back_populates="wards")
