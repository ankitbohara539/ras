from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


def _build_client() -> Client:
    settings = get_settings()
    if not settings.supabase_configured:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in backend/.env."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


@lru_cache
def get_supabase() -> Client:
    """The shared service-role client: storage, admin APIs, token verification.

    Built with the service-role key, so it bypasses Row Level Security. Only
    call it from trusted backend code.

    Never sign a user in on this client -- see `new_auth_client` below.
    """
    return _build_client()


def new_auth_client() -> Client:
    """A throwaway client for operations that sign a user in.

    `sign_in_with_password` stores the resulting session *on the client*, and
    every later call through that client then authenticates as that user
    rather than as the service role. On the shared client that is quietly
    catastrophic: one citizen logging in downgrades the whole process, and the
    next photo upload is rejected by Storage's row-level security.

    So sign-in gets its own instance, which is discarded with the session.
    """
    return _build_client()
