from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamped, UUIDPrimaryKey


class Category(UUIDPrimaryKey, Timestamped, Base):
    """An issue category.

    Each category carries its own deduplication geometry: a pothole only
    matches within a few dozen metres, while waterlogging spans a block.
    """

    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_ne: Mapped[str] = mapped_column(String(120), nullable=False)
    icon: Mapped[str] = mapped_column(String(48), nullable=False, default="alert")
    base_severity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    match_radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    dedupe_window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
