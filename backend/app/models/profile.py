from uuid import UUID

from sqlalchemy import Boolean, Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped
from app.models.enums import AccountStatus, Language, UserRole
from app.models.geography import Municipality, Ward


class Profile(Timestamped, Base):
    """Application-side user record, keyed by the Supabase auth.users id.

    Supabase owns credentials; this table owns role and geographic scope.
    """

    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32))
    # Stored in the existing private evidence bucket. The API only returns a
    # short-lived URL to the account owner (or an administrator), never a
    # browser-guessable public path.
    avatar_path: Mapped[str | None] = mapped_column(String(400))

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", native_enum=True),
        nullable=False,
        default=UserRole.CITIZEN,
        index=True,
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus, name="account_status", native_enum=True),
        nullable=False,
        default=AccountStatus.ACTIVE,
        index=True,
    )

    # Scope. An authority with ward_id set sees only that ward; an authority
    # with ward_id NULL sees every ward in its municipality. Admins see all.
    municipality_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("municipalities.id", ondelete="SET NULL"),
        index=True,
    )
    ward_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("wards.id", ondelete="SET NULL"),
        index=True,
    )

    preferred_language: Mapped[Language] = mapped_column(
        SAEnum(Language, name="language", native_enum=True),
        nullable=False,
        default=Language.EN,
    )
    large_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"),
    )

    municipality: Mapped["Municipality | None"] = relationship()
    ward: Mapped["Ward | None"] = relationship()
    approved_by: Mapped["Profile | None"] = relationship(remote_side=[id])

    @property
    def is_admin(self) -> bool:
        return self.role is UserRole.ADMIN

    @property
    def is_authority(self) -> bool:
        return self.role in (UserRole.AUTHORITY, UserRole.ADMIN)

    @property
    def is_active(self) -> bool:
        return self.account_status is AccountStatus.ACTIVE
