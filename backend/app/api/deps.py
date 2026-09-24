from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Car
from app.schemas.serializers import cars_out
from app.services.auth import user_id_from_token
from app.services.cars import CarChange, utcnow
from app.services.errors import Unauthorized
from app.services.permissions import Principal, load_principal
from app.ws.hub import CarBroadcast

bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_principal(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
    if credentials is None:
        raise Unauthorized("Faça login para continuar")
    return load_principal(db, user_id_from_token(credentials.credentials))


CurrentUser = Annotated[Principal, Depends(get_principal)]


def car_broadcast(db: Session, change: CarChange) -> CarBroadcast:
    """Serializa a mudança (depois do commit) para o hub transmitir."""
    car: Car = change.car
    db.refresh(car)
    out = cars_out(db, [car], utcnow())[0]
    return CarBroadcast(
        car=out.model_dump(mode="json"),
        task_type_id=car.task_type_id,
        event_type=change.event.type.value,
        status=car.status,
        floor_id=car.floor_id,
        previous_status=change.previous_status,
        previous_floor_id=change.previous_floor_id,
    )
