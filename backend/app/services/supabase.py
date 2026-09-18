from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Return a cached server-side Supabase client.

    Use this dependency only from trusted backend routes because it is created
    with the service-role key and therefore bypasses Row Level Security.
    """
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

