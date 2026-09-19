"""Authentication and authorisation dependencies.

The backend holds the service-role key, which bypasses Row Level Security, so
every access rule lives here. Nothing else in the app should decide who may
see what.
"""

import base64
import hashlib
import json
import threading
import time
from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.supabase import get_supabase
from app.db.session import get_db
from app.models.enums import AccountStatus, UserRole
from app.models.profile import Profile

bearer_scheme = HTTPBearer(auto_error=True)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token.",
    headers={"WWW-Authenticate": "Bearer"},
)


# Asking Supabase "who is this token?" is a network round trip (~250ms from
# here) on every single request, and a page makes several. A token Supabase
# has vouched for is remembered for a short while -- never past the token's
# own expiry -- keyed by a hash so raw tokens are not held in memory.
# The cost: a revoked session keeps working for at most this long.
_TOKEN_CACHE_SECONDS = 60
_token_cache: dict[str, tuple[UUID, float]] = {}
_token_lock = threading.Lock()


def _token_expiry(token: str) -> float | None:
    """The `exp` claim, read without verifying -- only used to cap the cache.

    Verification is Supabase's job and has already happened by the time this
    matters; a forged exp can only make the entry expire sooner, because the
    cache also never outlives _TOKEN_CACHE_SECONDS.
    """
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
        return float(exp) if exp is not None else None
    except (IndexError, ValueError, TypeError):
        return None


def _user_id_for(token: str) -> UUID:
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()

    with _token_lock:
        hit = _token_cache.get(key)
        if hit is not None and hit[1] > now:
            return hit[0]

    try:
        user_response = get_supabase().auth.get_user(token)
    except Exception as exc:
        raise CREDENTIALS_ERROR from exc

    user = getattr(user_response, "user", None)
    if user is None:
        raise CREDENTIALS_ERROR

    user_id = UUID(str(user.id))
    expires = now + _TOKEN_CACHE_SECONDS
    token_exp = _token_expiry(token)
    if token_exp is not None:
        expires = min(expires, token_exp)

    with _token_lock:
        if len(_token_cache) > 5000:
            _token_cache.clear()
        _token_cache[key] = (user_id, expires)
    return user_id


def get_current_profile(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    """Resolve the bearer token to an active Profile.

    Supabase verifies the token; the profile row supplies role and scope.
    """
    profile = db.get(Profile, _user_id_for(credentials.credentials))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no profile. Contact an administrator.",
        )

    if profile.account_status is not AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is {profile.account_status.value}.",
        )

    return profile


def require_roles(*roles: UserRole) -> Callable[[Profile], Profile]:
    """Dependency factory restricting a route to the given roles.

    Admin passes every check -- it is a superset of authority.
    """
    allowed = set(roles) | {UserRole.ADMIN}

    def dependency(profile: Profile = Depends(get_current_profile)) -> Profile:
        if profile.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return profile

    return dependency


require_citizen = require_roles(UserRole.CITIZEN)
require_authority = require_roles(UserRole.AUTHORITY)


def require_admin(profile: Profile = Depends(get_current_profile)) -> Profile:
    if profile.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return profile


def assert_can_access_ward(profile: Profile, ward_id: UUID | None) -> None:
    """Enforce ward isolation for authority accounts.

    Admin sees everything. An authority with ward_id set is confined to that
    ward; one with ward_id NULL covers every ward in its municipality.
    """
    if profile.role is UserRole.ADMIN:
        return

    if profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None and profile.ward_id != ward_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This report belongs to another ward.",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to perform this action.",
    )
