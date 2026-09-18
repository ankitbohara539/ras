"""The update schema is the access control for self-service profile edits."""

from app.schema.user import ProfileUpdateRequest


def test_profile_update_ignores_privileged_fields() -> None:
    data = ProfileUpdateRequest.model_validate(
        {
            "full_name": "New Name",
            "role": "admin",
            "account_status": "active",
            "municipality_id": "00000000-0000-0000-0000-000000000000",
        }
    )

    applied = data.model_dump(exclude_unset=True)
    assert applied == {"full_name": "New Name"}
    assert "role" not in applied
    assert "account_status" not in applied
    assert "municipality_id" not in applied
