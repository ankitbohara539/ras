from app.core.exceptions import ConflictError
from app.shared.infrastructure.models import EmergencyStatus

ALLOWED_EMERGENCY_TRANSITIONS = {
    EmergencyStatus.CREATED: {EmergencyStatus.ACKNOWLEDGED, EmergencyStatus.CANCELLED},
    EmergencyStatus.ACKNOWLEDGED: {EmergencyStatus.DISPATCHED, EmergencyStatus.CANCELLED},
    EmergencyStatus.DISPATCHED: {EmergencyStatus.ON_SCENE, EmergencyStatus.CANCELLED},
    EmergencyStatus.ON_SCENE: {EmergencyStatus.RESOLVED},
    EmergencyStatus.RESOLVED: set(),
    EmergencyStatus.CANCELLED: set(),
}


def ensure_emergency_transition(current: EmergencyStatus, target: EmergencyStatus) -> None:
    if target not in ALLOWED_EMERGENCY_TRANSITIONS[current]:
        raise ConflictError(f"Emergency cannot move from {current.value} to {target.value}.")
