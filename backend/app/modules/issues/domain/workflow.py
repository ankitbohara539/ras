from app.core.exceptions import ConflictError
from app.shared.infrastructure.models import IssueStatus

ALLOWED_TRANSITIONS: dict[IssueStatus, set[IssueStatus]] = {
    IssueStatus.REPORTED: {IssueStatus.VERIFIED, IssueStatus.REJECTED, IssueStatus.DUPLICATE},
    IssueStatus.VERIFIED: {IssueStatus.ASSIGNED, IssueStatus.REJECTED, IssueStatus.DUPLICATE},
    IssueStatus.ASSIGNED: {IssueStatus.IN_PROGRESS, IssueStatus.VERIFIED},
    IssueStatus.IN_PROGRESS: {IssueStatus.RESOLVED, IssueStatus.ASSIGNED},
    IssueStatus.RESOLVED: set(),
    IssueStatus.REJECTED: set(),
    IssueStatus.DUPLICATE: set(),
}


def ensure_issue_transition(current: IssueStatus, target: IssueStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ConflictError(f"Issue cannot move from {current.value} to {target.value}.")
