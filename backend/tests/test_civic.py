"""Civic complaints are private: these pin down exactly who can see and act."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import CivicStatus, UserRole
from app.services.civic_service import can_manage, can_view, update_status

WARD, OTHER_WARD, MUNI, OTHER_MUNI = uuid4(), uuid4(), uuid4(), uuid4()


def person(role, ward_id=None, municipality_id=None):
    return SimpleNamespace(id=uuid4(), role=role, ward_id=ward_id, municipality_id=municipality_id)


def complaint(reporter, status=CivicStatus.SUBMITTED):
    return SimpleNamespace(
        id=uuid4(),
        public_code="CIV-KMC-08-000001",
        reporter_id=reporter.id,
        ward_id=WARD,
        municipality_id=MUNI,
        status=status,
        action_note=None,
        reviewed_by_id=None,
        reviewed_at=None,
    )


class _DB:
    def add(self, obj):
        pass

    def flush(self):
        pass


class TestVisibility:
    def test_reporter_sees_but_cannot_act(self) -> None:
        reporter = person(UserRole.CITIZEN, municipality_id=MUNI)
        c = complaint(reporter)
        assert can_view(reporter, c) and not can_manage(reporter, c)

    def test_other_citizens_never_see_it(self) -> None:
        c = complaint(person(UserRole.CITIZEN))
        neighbour = person(UserRole.CITIZEN, ward_id=WARD, municipality_id=MUNI)
        assert not can_view(neighbour, c)

    def test_only_the_right_office(self) -> None:
        c = complaint(person(UserRole.CITIZEN))
        assert can_manage(person(UserRole.AUTHORITY, ward_id=WARD, municipality_id=MUNI), c)
        assert can_manage(person(UserRole.AUTHORITY, municipality_id=MUNI), c)
        assert not can_manage(person(UserRole.AUTHORITY, ward_id=OTHER_WARD, municipality_id=MUNI), c)
        assert not can_manage(person(UserRole.AUTHORITY, municipality_id=OTHER_MUNI), c)
        assert can_manage(person(UserRole.ADMIN), c)


class TestDecisions:
    officer = person(UserRole.AUTHORITY, ward_id=WARD, municipality_id=MUNI)

    def test_closing_needs_a_note(self) -> None:
        c = complaint(person(UserRole.CITIZEN))
        with pytest.raises(HTTPException) as err:
            update_status(_DB(), self.officer, c, CivicStatus.ACTION_TAKEN, "  ")
        assert err.value.status_code == 422

    def test_action_taken_records_the_note(self) -> None:
        c = complaint(person(UserRole.CITIZEN))
        update_status(_DB(), self.officer, c, CivicStatus.ACTION_TAKEN, "Fined Rs 500")
        assert c.status is CivicStatus.ACTION_TAKEN and c.action_note == "Fined Rs 500"
        assert c.reviewed_by_id == self.officer.id

    def test_closed_can_only_be_reopened(self) -> None:
        c = complaint(person(UserRole.CITIZEN), status=CivicStatus.DISMISSED)
        with pytest.raises(HTTPException) as err:
            update_status(_DB(), self.officer, c, CivicStatus.ACTION_TAKEN, "x")
        assert err.value.status_code == 409
        update_status(_DB(), self.officer, c, CivicStatus.UNDER_REVIEW, None)
        assert c.status is CivicStatus.UNDER_REVIEW

    def test_wrong_ward_cannot_decide(self) -> None:
        c = complaint(person(UserRole.CITIZEN))
        stranger = person(UserRole.AUTHORITY, ward_id=OTHER_WARD, municipality_id=MUNI)
        with pytest.raises(HTTPException) as err:
            update_status(_DB(), stranger, c, CivicStatus.DISMISSED, "no")
        assert err.value.status_code == 403
