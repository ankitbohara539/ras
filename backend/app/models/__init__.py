"""SQLAlchemy models.

Importing this package registers every table on Base.metadata, which is what
Alembic autogenerate walks. Any new model file must be imported here.
"""

from app.db.base import Base
from app.models.category import Category
from app.models.emergency import Alert, CivicService, SosRequest
from app.models.enums import (
    AccountStatus,
    AlertSeverity,
    AlertTargetType,
    CandidateStatus,
    EmergencyType,
    Language,
    MunicipalityType,
    NotificationType,
    ServiceType,
    SosStatus,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.geography import Municipality, Ward
from app.models.notification import Notification
from app.models.profile import Profile
from app.models.ticket import (
    EMBEDDING_DIM,
    DuplicateCandidate,
    Ticket,
    TicketCorroboration,
    TicketPhoto,
    TicketStatusHistory,
)

__all__ = [
    "EMBEDDING_DIM",
    "AccountStatus",
    "Alert",
    "AlertSeverity",
    "AlertTargetType",
    "Base",
    "CandidateStatus",
    "Category",
    "CivicService",
    "DuplicateCandidate",
    "EmergencyType",
    "Language",
    "Municipality",
    "MunicipalityType",
    "Notification",
    "NotificationType",
    "Profile",
    "ServiceType",
    "SosRequest",
    "SosStatus",
    "Ticket",
    "TicketCorroboration",
    "TicketPhoto",
    "TicketPriority",
    "TicketStatus",
    "TicketStatusHistory",
    "UserRole",
    "Ward",
]
