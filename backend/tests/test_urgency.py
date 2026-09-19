"""Comment pressure: reading urgency out of comments, and what it does to
priority. Plus the auto-merge threshold, which is the other place the system
now acts without waiting for an officer.

Pure functions and a stub session -- no database, same as test_priority.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ml.urgency import is_urgent
from app.models.enums import CandidateStatus, TicketPriority, TicketStatus
from app.services.ticket_service import (
    apply_priority,
    auto_merge_if_confident,
    escalate_for_comments,
)


class TestDetector:
    @pytest.mark.parametrize(
        "text",
        [
            "This should be fixed soon, it is a major issue",
            "URGENT please fix it now",
            "Someone will get hurt here",
            "Two bikes had an accident here yesterday",
            "Very dangerous at night",
            "It has been weeks and still not fixed",
            "कृपया चाँडै बनाइदिनुहोस्",
            "यो ठूलो समस्या हो",
            "yo khaldo chhito banaideu",
            "jaruri cha",
            # Everyday complaints and requests, no "urgent" anywhere -- the
            # three comments on KMC-07-000006 were all of this kind.
            "fix this,it has been quite a headache",
            "solve this problem urgent",
            "yeah rn this is a problem please fix ward 7",
            "When will this be fixed?",
            "Please repair the road",
            "It is a big problem for school kids",
            "cannot walk here at night",
            "yo samasya kahile banchha",
            "सडक कहिले बन्छ? धेरै दुःख भयो",
        ],
    )
    def test_urgent_comments(self, text: str) -> None:
        assert is_urgent(text)

    @pytest.mark.parametrize(
        "text",
        [
            "I saw this too",
            "Thanks for reporting",
            "Is this the one near the bus stop?",
            "I think it was fixed already",
            "Same one as last week",
            "मैले पनि देखें",
            "धन्यवाद",
            "",
        ],
    )
    def test_ordinary_comments(self, text: str) -> None:
        assert not is_urgent(text)


class TestCommentEscalation:
    def test_fewer_than_three_people_change_nothing(self) -> None:
        assert escalate_for_comments(TicketPriority.LOW, 0) is TicketPriority.LOW
        assert escalate_for_comments(TicketPriority.LOW, 2) is TicketPriority.LOW

    def test_three_people_raise_one_level(self) -> None:
        assert escalate_for_comments(TicketPriority.LOW, 3) is TicketPriority.MEDIUM
        assert escalate_for_comments(TicketPriority.MEDIUM, 3) is TicketPriority.HIGH

    def test_six_people_raise_two_levels(self) -> None:
        assert escalate_for_comments(TicketPriority.LOW, 5) is TicketPriority.MEDIUM
        assert escalate_for_comments(TicketPriority.LOW, 6) is TicketPriority.HIGH

    def test_stops_at_high(self) -> None:
        assert escalate_for_comments(TicketPriority.MEDIUM, 30) is TicketPriority.HIGH
        assert escalate_for_comments(TicketPriority.HIGH, 30) is TicketPriority.HIGH

    def test_never_touches_critical(self) -> None:
        assert escalate_for_comments(TicketPriority.CRITICAL, 30) is (
            TicketPriority.CRITICAL
        )


def make_ticket(**overrides):
    base = dict(
        child_count=0,
        corroboration_count=0,
        dispute_count=0,
        community_verified=False,
        urgent_commenter_count=0,
        priority=TicketPriority.LOW,
        priority_locked=False,
        status=TicketStatus.REPORTED,
        created_at=datetime.now(UTC),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestApplyPriorityWithComments:
    def test_low_pothole_with_three_urgent_commenters_becomes_medium(self) -> None:
        category = SimpleNamespace(base_severity=0.45)
        assert apply_priority(make_ticket(), category) is TicketPriority.LOW
        assert apply_priority(
            make_ticket(urgent_commenter_count=3), category
        ) is TicketPriority.MEDIUM

    def test_a_locked_ticket_ignores_comments(self) -> None:
        ticket = make_ticket(
            priority=TicketPriority.LOW,
            priority_locked=True,
            urgent_commenter_count=9,
        )
        assert apply_priority(ticket, SimpleNamespace(base_severity=0.45)) is (
            TicketPriority.LOW
        )


# ------------------------------------------------------------ auto-merge


class _Query:
    def filter(self, *args):
        return self

    def update(self, values):
        return 0


class _Session:
    """Just enough of a Session for the merge path to run."""

    def __init__(self, *objects):
        self.objects = {obj.id: obj for obj in objects}
        self.added = []

    def get(self, model, key):
        return self.objects.get(key)

    def query(self, model):
        return _Query()

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass


def make_pair():
    category = SimpleNamespace(id=uuid4(), base_severity=0.60)
    parent = make_ticket(
        id=uuid4(),
        public_code="KMC-05-000001",
        parent_id=None,
        reporter_id=uuid4(),
        category_id=category.id,
        priority=TicketPriority.MEDIUM,
    )
    child = make_ticket(
        id=uuid4(),
        public_code="KMC-05-000002",
        parent_id=None,
        reporter_id=uuid4(),
        category_id=category.id,
    )
    return category, parent, child


def suggestion(child, parent, score, distance_m=10.0):
    return SimpleNamespace(
        ticket_id=child.id,
        candidate_ticket_id=parent.id,
        score=score,
        distance_m=distance_m,
        status=CandidateStatus.PENDING,
    )


@pytest.fixture(autouse=True)
def pothole_radius(monkeypatch):
    """Every category in these tests matches within 60 m, like potholes."""
    from app.services import ticket_service

    class Radii(dict):
        def get(self, key, default=None):
            return 60

    monkeypatch.setattr(ticket_service, "category_radii", lambda db: Radii())


class TestAutoMerge:
    def test_eighty_percent_merges(self) -> None:
        category, parent, child = make_pair()
        db = _Session(category, parent, child)

        result = auto_merge_if_confident(db, child, [suggestion(child, parent, 0.80)])

        assert result is not None and result[0] is parent
        assert child.parent_id == parent.id
        assert child.status is TicketStatus.MERGED
        assert parent.child_count == 1

    def test_below_eighty_percent_waits_for_a_human(self) -> None:
        category, parent, child = make_pair()
        db = _Session(category, parent, child)

        assert auto_merge_if_confident(db, child, [suggestion(child, parent, 0.79)]) is None
        assert child.parent_id is None
        assert parent.child_count == 0

    def test_picks_the_best_match(self) -> None:
        category, parent, child = make_pair()
        _, weaker, _ = make_pair()
        weaker.category_id = category.id
        db = _Session(category, parent, weaker, child)

        result = auto_merge_if_confident(
            db,
            child,
            [suggestion(child, weaker, 0.82), suggestion(child, parent, 0.93)],
        )

        assert result is not None and result[0] is parent

    def test_never_merges_into_a_closed_ticket(self) -> None:
        category, parent, child = make_pair()
        parent.status = TicketStatus.RESOLVED
        db = _Session(category, parent, child)

        assert auto_merge_if_confident(db, child, [suggestion(child, parent, 0.95)]) is None
        assert child.parent_id is None

    def test_never_merges_a_citizens_report_into_their_own(self) -> None:
        # Two reports filed together from one spot are two problems.
        category, parent, child = make_pair()
        parent.reporter_id = child.reporter_id
        db = _Session(category, parent, child)

        assert auto_merge_if_confident(db, child, [suggestion(child, parent, 0.95)]) is None
        assert child.parent_id is None

    def test_skips_own_report_but_merges_into_someone_elses(self) -> None:
        category, own, child = make_pair()
        own.reporter_id = child.reporter_id
        _, other, _ = make_pair()
        other.category_id = category.id
        db = _Session(category, own, other, child)

        result = auto_merge_if_confident(
            db, child, [suggestion(child, own, 0.97), suggestion(child, other, 0.85)]
        )
        assert result is not None and result[0] is other

    def test_gps_slack_band_is_suggested_but_never_auto_merged(self) -> None:
        # 68 m apart with a 60 m radius: within the GPS allowance, so the
        # officer sees it -- but automation only acts inside the radius.
        category, parent, child = make_pair()
        db = _Session(category, parent, child)

        assert auto_merge_if_confident(
            db, child, [suggestion(child, parent, 0.95, distance_m=68.0)]
        ) is None
        assert child.parent_id is None
