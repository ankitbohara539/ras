"""Priority: the score, the age ladder, and the human override.

These run against plain objects -- no database -- because the rules are pure
functions and that is the point of keeping them that way.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.enums import TicketPriority, TicketStatus
from app.services.ticket_service import (
    apply_priority,
    compute_priority,
    escalate_for_age,
)


def make_ticket(**overrides):
    base = dict(
        child_count=0,
        corroboration_count=0,
        dispute_count=0,
        community_verified=False,
        priority=TicketPriority.LOW,
        priority_locked=False,
        status=TicketStatus.REPORTED,
        created_at=datetime.now(UTC),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_category(base_severity: float):
    return SimpleNamespace(base_severity=base_severity)


def days_ago(n: float) -> datetime:
    return datetime.now(UTC) - timedelta(days=n)


class TestScoredPriority:
    def test_category_severity_sets_the_floor(self) -> None:
        # A live power line is high on category alone; nobody has to confirm it.
        assert compute_priority(make_ticket(), make_category(0.80)) is (
            TicketPriority.HIGH
        )
        assert compute_priority(make_ticket(), make_category(0.40)) is (
            TicketPriority.LOW
        )

    def test_duplicates_raise_priority(self) -> None:
        category = make_category(0.50)
        one = compute_priority(make_ticket(), category)
        many = compute_priority(make_ticket(child_count=5), category)
        assert one is TicketPriority.MEDIUM
        assert many is TicketPriority.HIGH

    def test_fan_in_is_capped(self) -> None:
        """A hundred pothole reports must not outrank a gas leak."""
        category = make_category(0.50)
        popular = compute_priority(make_ticket(child_count=100), category)
        dangerous = compute_priority(make_ticket(), make_category(0.85))
        assert popular is TicketPriority.HIGH
        assert dangerous is TicketPriority.HIGH

    def test_disputes_pull_it_down(self) -> None:
        category = make_category(0.55)
        assert compute_priority(make_ticket(), category) is TicketPriority.MEDIUM
        assert (
            compute_priority(make_ticket(dispute_count=3), category)
            is TicketPriority.LOW
        )


class TestAgeLadder:
    def test_fresh_ticket_does_not_escalate(self) -> None:
        result = escalate_for_age(
            TicketPriority.LOW, days_ago(2), TicketStatus.REPORTED
        )
        assert result is TicketPriority.LOW

    def test_low_becomes_medium_after_seven_days(self) -> None:
        assert (
            escalate_for_age(TicketPriority.LOW, days_ago(7), TicketStatus.REPORTED)
            is TicketPriority.MEDIUM
        )

    def test_low_becomes_high_after_ten_days(self) -> None:
        """Seven days to medium, three more to high."""
        assert (
            escalate_for_age(TicketPriority.LOW, days_ago(9), TicketStatus.REPORTED)
            is TicketPriority.MEDIUM
        )
        assert (
            escalate_for_age(TicketPriority.LOW, days_ago(10), TicketStatus.REPORTED)
            is TicketPriority.HIGH
        )

    def test_medium_becomes_high_after_three_days(self) -> None:
        assert (
            escalate_for_age(TicketPriority.MEDIUM, days_ago(2), TicketStatus.REPORTED)
            is TicketPriority.MEDIUM
        )
        assert (
            escalate_for_age(TicketPriority.MEDIUM, days_ago(3), TicketStatus.REPORTED)
            is TicketPriority.HIGH
        )

    def test_escalation_stops_at_high(self) -> None:
        """Age is not danger. Only a human promotes to critical."""
        assert (
            escalate_for_age(TicketPriority.HIGH, days_ago(400), TicketStatus.REPORTED)
            is TicketPriority.HIGH
        )

    @pytest.mark.parametrize(
        "closed",
        [TicketStatus.RESOLVED, TicketStatus.REJECTED, TicketStatus.MERGED],
    )
    def test_closed_tickets_never_escalate(self, closed: TicketStatus) -> None:
        assert escalate_for_age(TicketPriority.LOW, days_ago(90), closed) is (
            TicketPriority.LOW
        )

    def test_in_progress_still_escalates(self) -> None:
        """Being worked on is not the same as being finished."""
        assert (
            escalate_for_age(
                TicketPriority.LOW, days_ago(10), TicketStatus.IN_PROGRESS
            )
            is TicketPriority.HIGH
        )


class TestApplyPriority:
    def test_combines_score_and_age(self) -> None:
        ticket = make_ticket(created_at=days_ago(8))
        apply_priority(ticket, make_category(0.40))
        assert ticket.priority is TicketPriority.MEDIUM

    def test_a_locked_ticket_is_left_alone(self) -> None:
        """The whole point of the override: automation must not undo it."""
        ticket = make_ticket(
            created_at=days_ago(30),
            priority=TicketPriority.LOW,
            priority_locked=True,
            child_count=20,
        )
        apply_priority(ticket, make_category(0.85))
        assert ticket.priority is TicketPriority.LOW

    def test_score_still_wins_when_higher_than_the_ladder(self) -> None:
        ticket = make_ticket(created_at=days_ago(8), child_count=6)
        apply_priority(ticket, make_category(0.75))
        assert ticket.priority is TicketPriority.CRITICAL
