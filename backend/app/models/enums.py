from enum import StrEnum


class UserRole(StrEnum):
    CITIZEN = "citizen"
    AUTHORITY = "authority"
    ADMIN = "admin"


class AccountStatus(StrEnum):
    """Authority accounts start pending until an admin approves them."""

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class Language(StrEnum):
    EN = "en"
    NE = "ne"


class MunicipalityType(StrEnum):
    METROPOLITAN = "metropolitan"
    SUB_METROPOLITAN = "sub_metropolitan"
    MUNICIPALITY = "municipality"
    RURAL_MUNICIPALITY = "rural_municipality"


class TicketStatus(StrEnum):
    REPORTED = "reported"
    VERIFIED = "verified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    MERGED = "merged"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CandidateStatus(StrEnum):
    """Lifecycle of a duplicate suggestion produced by the matcher."""

    PENDING = "pending"
    MERGED = "merged"
    REJECTED = "rejected"


class EmergencyType(StrEnum):
    MEDICAL = "medical"
    FIRE = "fire"
    POLICE = "police"
    DISASTER = "disaster"
    OTHER = "other"


class SosStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    DISPATCHED = "dispatched"
    CLOSED = "closed"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertTargetType(StrEnum):
    WARD = "ward"
    RADIUS = "radius"


class ServiceType(StrEnum):
    HOSPITAL = "hospital"
    AMBULANCE = "ambulance"
    POLICE = "police"
    FIRE = "fire"
    WARD_OFFICE = "ward_office"
    MUNICIPALITY_OFFICE = "municipality_office"
    SHELTER = "shelter"
    PHARMACY = "pharmacy"
    OTHER = "other"


class NotificationType(StrEnum):
    TICKET_STATUS_CHANGED = "ticket_status_changed"
    TICKET_MERGED = "ticket_merged"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_CORROBORATED = "ticket_corroborated"
    TICKET_COMMENTED = "ticket_commented"
    ALERT_PUBLISHED = "alert_published"
    ACCOUNT_APPROVED = "account_approved"
