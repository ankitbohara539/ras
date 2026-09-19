"""can_view_ticket is the single-row twin of scope_filter -- comments and the
single-ticket GET both depend on it, so its rules are worth pinning down."""

from types import SimpleNamespace
from uuid import uuid4

from app.models.enums import UserRole
from app.services.ticket_service import can_view_ticket


def make_profile(role: UserRole, ward_id=None, municipality_id=None):
    return SimpleNamespace(role=role, ward_id=ward_id, municipality_id=municipality_id)


def make_ticket(ward_id, municipality_id):
    return SimpleNamespace(ward_id=ward_id, municipality_id=municipality_id)


class TestAdmin:
    def test_sees_everything(self) -> None:
        admin = make_profile(UserRole.ADMIN)
        ticket = make_ticket(uuid4(), uuid4())
        assert can_view_ticket(admin, ticket) is True


class TestAuthority:
    def test_ward_scoped_authority_confined_to_its_ward(self) -> None:
        ward = uuid4()
        other_ward = uuid4()
        municipality = uuid4()
        authority = make_profile(UserRole.AUTHORITY, ward_id=ward, municipality_id=municipality)

        assert can_view_ticket(authority, make_ticket(ward, municipality)) is True
        assert can_view_ticket(authority, make_ticket(other_ward, municipality)) is False

    def test_municipality_scoped_authority_sees_every_ward(self) -> None:
        municipality = uuid4()
        authority = make_profile(UserRole.AUTHORITY, ward_id=None, municipality_id=municipality)

        assert can_view_ticket(authority, make_ticket(uuid4(), municipality)) is True
        assert can_view_ticket(authority, make_ticket(uuid4(), uuid4())) is False

    def test_unscoped_authority_sees_nothing(self) -> None:
        """Mirrors scope_filter's `Ticket.id.is_(None)` -- no scope, no access."""
        authority = make_profile(UserRole.AUTHORITY, ward_id=None, municipality_id=None)
        assert can_view_ticket(authority, make_ticket(uuid4(), uuid4())) is False


class TestCitizen:
    def test_confined_to_their_municipality(self) -> None:
        municipality = uuid4()
        citizen = make_profile(UserRole.CITIZEN, municipality_id=municipality)

        assert can_view_ticket(citizen, make_ticket(uuid4(), municipality)) is True
        assert can_view_ticket(citizen, make_ticket(uuid4(), uuid4())) is False

    def test_a_citizen_with_no_municipality_sees_all(self) -> None:
        """Matches scope_filter's `return []` -- an unset municipality is not scoped."""
        citizen = make_profile(UserRole.CITIZEN, municipality_id=None)
        assert can_view_ticket(citizen, make_ticket(uuid4(), uuid4())) is True
