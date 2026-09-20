"""SOS, public alerts and the notification feed.

Delivery is in-app: clients poll these endpoints. Supabase Realtime was the
obvious alternative, but Realtime authorises through RLS, and every table here
has RLS on with no policies precisely so the browser cannot read them
directly. Opening policies just for Realtime would mean re-implementing the
ward-scoping rules in SQL alongside the Python ones -- two copies of the
authorisation logic, which is how they drift apart. Polling a scoped endpoint
keeps one copy.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.geo import haversine_m
from app.core.security import get_current_profile, require_authority
from app.db.session import get_db
from app.models.emergency import Alert, CivicService, SosRequest
from app.models.enums import (
    AlertTargetType,
    NotificationType,
    ServiceType,
    SosStatus,
    UserRole,
)
from app.models.notification import Notification
from app.models.profile import Profile
from app.schema.emergency import (
    AlertCreateRequest,
    AlertResponse,
    NotificationListResponse,
    NotificationResponse,
    SosCreateRequest,
    SosCreateResponse,
    SosResponse,
    SosUpdateRequest,
)
from app.services.ticket_service import resolve_ward

router = APIRouter(tags=["Emergency"])

EMERGENCY_SERVICE_TYPES = (
    ServiceType.POLICE,
    ServiceType.AMBULANCE,
    ServiceType.FIRE,
)


def _now() -> datetime:
    return datetime.now(UTC)


# -------------------------------------------------------------------- SOS


@router.post(
    "/sos", response_model=SosCreateResponse, status_code=status.HTTP_201_CREATED
)
def raise_sos(
    data: SosCreateRequest,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> SosCreateResponse:
    """One-tap emergency request.

    Never deduplicated and never merged: an SOS that gets folded under another
    is an SOS nobody answers.
    """
    ward = resolve_ward(db, data.latitude, data.longitude)

    sos = SosRequest(
        citizen_id=profile.id,
        emergency_type=data.emergency_type,
        latitude=data.latitude,
        longitude=data.longitude,
        address_text=data.address_text,
        ward_id=ward.id,
        municipality_id=ward.municipality_id,
        note=data.note,
        contact_phone=data.contact_phone or profile.phone,
        status=SosStatus.OPEN,
    )
    db.add(sos)
    db.flush()

    contacts = db.scalars(
        select(CivicService)
        .where(
            CivicService.is_emergency.is_(True),
            CivicService.service_type.in_(EMERGENCY_SERVICE_TYPES),
        )
        .limit(20)
    ).all()

    nearest = []
    for service in contacts:
        distance = None
        if service.latitude is not None and service.longitude is not None:
            distance = round(
                haversine_m(
                    data.latitude, data.longitude, service.latitude, service.longitude
                ),
                1,
            )
        nearest.append(
            {
                "name_en": service.name_en,
                "name_ne": service.name_ne,
                "service_type": service.service_type.value,
                "phone": service.phone,
                "distance_m": distance,
            }
        )
    nearest.sort(key=lambda c: (c["distance_m"] is not None, c["distance_m"] or 0))

    response = SosResponse.model_validate(sos)
    response.citizen_name = profile.full_name
    response.citizen_phone = profile.phone

    return SosCreateResponse(
        sos=response,
        emergency_contacts=nearest[:8],
        message=(
            "Your emergency request has been sent to the ward authority. "
            "If this is life-threatening, call the numbers below now."
        ),
    )


@router.get("/sos", response_model=list[SosResponse])
def list_sos(
    status_filter: SosStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> list[SosResponse]:
    """Citizens see their own requests; authorities see their ward's."""
    filters = []

    if profile.role is UserRole.CITIZEN:
        filters.append(SosRequest.citizen_id == profile.id)
    elif profile.role is UserRole.AUTHORITY:
        if profile.ward_id is not None:
            filters.append(SosRequest.ward_id == profile.ward_id)
        elif profile.municipality_id is not None:
            filters.append(SosRequest.municipality_id == profile.municipality_id)

    if status_filter is not None:
        filters.append(SosRequest.status == status_filter)

    rows = db.scalars(
        select(SosRequest)
        .where(*filters)
        .order_by(SosRequest.created_at.desc())
        .limit(limit)
    ).all()

    responses = []
    for sos in rows:
        item = SosResponse.model_validate(sos)
        citizen = db.get(Profile, sos.citizen_id)
        if citizen is not None:
            item.citizen_name = citizen.full_name
            item.citizen_phone = citizen.phone
        responses.append(item)

    return responses


@router.patch("/sos/{sos_id}", response_model=SosResponse)
def update_sos(
    sos_id: UUID,
    data: SosUpdateRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> SosResponse:
    sos = db.get(SosRequest, sos_id)
    if sos is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such SOS request."
        )

    if (
        authority.role is UserRole.AUTHORITY
        and authority.ward_id is not None
        and sos.ward_id != authority.ward_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This request belongs to another ward.",
        )

    sos.status = data.status
    if data.resolution_note:
        sos.resolution_note = data.resolution_note

    if data.status is SosStatus.ACKNOWLEDGED and sos.acknowledged_at is None:
        sos.acknowledged_at = _now()
        sos.acknowledged_by_id = authority.id
    if data.status is SosStatus.CLOSED:
        sos.closed_at = _now()

    db.add(
        Notification(
            user_id=sos.citizen_id,
            type=NotificationType.TICKET_STATUS_CHANGED,
            title_en=f"Your emergency request is {data.status.value}",
            title_ne="तपाईंको आपतकालीन अनुरोधको अवस्था परिवर्तन भयो",
            body_en=data.resolution_note,
            sos_request_id=sos.id,
        )
    )
    db.flush()

    response = SosResponse.model_validate(sos)
    citizen = db.get(Profile, sos.citizen_id)
    if citizen is not None:
        response.citizen_name = citizen.full_name
        response.citizen_phone = citizen.phone
    return response


# ----------------------------------------------------------------- alerts


@router.post(
    "/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED
)
def publish_alert(
    data: AlertCreateRequest,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> AlertResponse:
    if authority.municipality_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Your account is not attached to a municipality.",
        )

    alert = Alert(
        created_by_id=authority.id,
        municipality_id=authority.municipality_id,
        title_en=data.title_en,
        title_ne=data.title_ne,
        body_en=data.body_en,
        body_ne=data.body_ne,
        instructions_en=data.instructions_en,
        instructions_ne=data.instructions_ne,
        severity=data.severity,
        target_type=data.target_type,
        ward_ids=data.ward_ids,
        center_lat=data.center_lat,
        center_lon=data.center_lon,
        radius_m=data.radius_m,
        starts_at=data.starts_at or _now(),
        expires_at=data.expires_at,
        is_active=True,
    )
    db.add(alert)
    db.flush()

    # Fan out to everyone in the targeted wards. Radius-targeted alerts are
    # matched at read time instead, since a citizen's position moves.
    if data.target_type is AlertTargetType.WARD and data.ward_ids:
        recipients = db.scalars(
            select(Profile).where(Profile.ward_id.in_(data.ward_ids))
        ).all()
        for recipient in recipients:
            db.add(
                Notification(
                    user_id=recipient.id,
                    type=NotificationType.ALERT_PUBLISHED,
                    title_en=data.title_en,
                    title_ne=data.title_ne,
                    body_en=data.body_en,
                    alert_id=alert.id,
                )
            )
        db.flush()

    return AlertResponse.model_validate(alert)


@router.get("/alerts", response_model=list[AlertResponse])
def list_alerts(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    include_expired: bool = False,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> list[AlertResponse]:
    """Alerts that apply to this citizen, by ward membership or by position."""
    filters = [Alert.is_active.is_(True)]
    if not include_expired:
        filters.append(
            or_(Alert.expires_at.is_(None), Alert.expires_at > _now())
        )
    if profile.municipality_id is not None and profile.role is UserRole.CITIZEN:
        filters.append(Alert.municipality_id == profile.municipality_id)

    rows = db.scalars(
        select(Alert).where(*filters).order_by(Alert.created_at.desc()).limit(100)
    ).all()

    applicable = []
    for alert in rows:
        response = AlertResponse.model_validate(alert)

        if alert.target_type is AlertTargetType.WARD:
            if profile.role is not UserRole.CITIZEN:
                applicable.append(response)
            elif profile.ward_id and alert.ward_ids:
                if profile.ward_id in alert.ward_ids:
                    applicable.append(response)
            continue

        # Radius-targeted: include when the caller is inside the circle, or
        # when they sent no position at all (better a spurious alert than a
        # missed one).
        if latitude is None or longitude is None:
            applicable.append(response)
            continue

        if alert.center_lat is None or alert.center_lon is None:
            continue

        distance = haversine_m(
            latitude, longitude, alert.center_lat, alert.center_lon
        )
        response.distance_m = round(distance, 1)
        if distance <= (alert.radius_m or 0):
            applicable.append(response)

    return applicable


@router.patch("/alerts/{alert_id}/deactivate", response_model=AlertResponse)
def deactivate_alert(
    alert_id: UUID,
    authority: Profile = Depends(require_authority),
    db: Session = Depends(get_db),
) -> AlertResponse:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such alert."
        )

    alert.is_active = False
    db.flush()
    return AlertResponse.model_validate(alert)


# ---------------------------------------------------------- notifications


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    filters = [Notification.user_id == profile.id]
    if unread_only:
        filters.append(Notification.read_at.is_(None))

    rows = db.scalars(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()

    # When the page holds every matching row, count from it instead of
    # asking the database again. The badge polls this every 30 seconds.
    if len(rows) < limit:
        unread = sum(1 for n in rows if n.read_at is None)
    else:
        unread = db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == profile.id, Notification.read_at.is_(None))
        ) or 0

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in rows],
        unread=unread,
    )


@router.post("/notifications/read", response_model=NotificationListResponse)
def mark_read(
    notification_ids: list[UUID] | None = None,
    profile: Profile = Depends(get_current_profile),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Mark the given notifications read, or all of them when none are given."""
    filters = [Notification.user_id == profile.id, Notification.read_at.is_(None)]
    if notification_ids:
        filters.append(Notification.id.in_(notification_ids))

    db.query(Notification).filter(*filters).update(
        {"read_at": _now()}, synchronize_session=False
    )
    db.flush()

    return list_notifications(unread_only=False, limit=50, profile=profile, db=db)
