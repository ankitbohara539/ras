from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import event_bus
from app.core.exceptions import AuthorizationError
from app.modules.auth.presentation.dependencies import CurrentUser, require_any_role
from app.modules.emergency.application.service import EmergencyService, SOSCreate, SOSResponse
from app.shared.infrastructure.models import EmergencySOS, EmergencyStatus, RoleCode

router = APIRouter(prefix="/emergencies", tags=["emergencies"])


def service(db: AsyncSession = Depends(get_db)) -> EmergencyService:
    return EmergencyService(db, event_bus)


@router.post("/sos", response_model=SOSResponse, status_code=201)
async def create_sos(
    payload: SOSCreate,
    current: CurrentUser,
    use_case: Annotated[EmergencyService, Depends(service)],
) -> SOSResponse:
    return SOSResponse.model_validate(await use_case.create(current.id, payload))


@router.get("", response_model=list[SOSResponse])
async def list_emergencies(
    current=Depends(require_any_role(RoleCode.RESPONDER, RoleCode.ADMIN)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
) -> list[SOSResponse]:
    rows = (
        await db.execute(
            select(EmergencySOS)
            .where(EmergencySOS.status.not_in([EmergencyStatus.RESOLVED, EmergencyStatus.CANCELLED]))
            .order_by(EmergencySOS.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [SOSResponse.model_validate(row) for row in rows]


@router.get("/{emergency_id}", response_model=SOSResponse)
async def get_emergency(
    emergency_id: str,
    current: CurrentUser,
    use_case: Annotated[EmergencyService, Depends(service)],
) -> SOSResponse:
    sos = await use_case.get(emergency_id)
    if current.id != sos.user_id and not set(current.roles).intersection(
        {RoleCode.RESPONDER, RoleCode.ADMIN}
    ):
        raise AuthorizationError()
    return SOSResponse.model_validate(sos)


def transition_route(path: str, target: EmergencyStatus):
    async def handler(
        emergency_id: str,
        expected_version: int,
        current=Depends(require_any_role(RoleCode.RESPONDER, RoleCode.ADMIN)),
        use_case: EmergencyService = Depends(service),
    ) -> SOSResponse:
        result = await use_case.transition(emergency_id, current.id, target, expected_version)
        return SOSResponse.model_validate(result)

    router.add_api_route(path, handler, methods=["POST"], response_model=SOSResponse)


transition_route("/{emergency_id}/acknowledge", EmergencyStatus.ACKNOWLEDGED)
transition_route("/{emergency_id}/dispatch", EmergencyStatus.DISPATCHED)
transition_route("/{emergency_id}/on-scene", EmergencyStatus.ON_SCENE)
transition_route("/{emergency_id}/resolve", EmergencyStatus.RESOLVED)


@router.post("/{emergency_id}/cancel", response_model=SOSResponse)
async def cancel_emergency(
    emergency_id: str,
    expected_version: int,
    current: CurrentUser,
    use_case: Annotated[EmergencyService, Depends(service)],
) -> SOSResponse:
    sos = await use_case.get(emergency_id)
    if sos.user_id != current.id and RoleCode.ADMIN not in current.roles:
        raise AuthorizationError()
    return SOSResponse.model_validate(
        await use_case.transition(emergency_id, current.id, EmergencyStatus.CANCELLED, expected_version)
    )
