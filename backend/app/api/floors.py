from fastapi import APIRouter, BackgroundTasks

from app.api.deps import DB, CurrentUser
from app.schemas.car import CarOut
from app.schemas.floor import FloorCapacityIn, FloorDetail, FloorSummary
from app.schemas.serializers import cars_out, floor_detail, floor_summary
from app.services import cars as car_service
from app.services import floors as floor_service
from app.services.cars import utcnow
from app.services.permissions import ensure_can_view_floor
from app.ws.hub import hub

router = APIRouter(prefix="/floors", tags=["floors"])


@router.get("")
def list_floors(db: DB, p: CurrentUser) -> list[FloorSummary]:
    floors = floor_service.visible_floors(db, p)
    counts = floor_service.occupied_counts(db, [f.id for f in floors])
    return [floor_summary(f, counts.get(f.id, 0)) for f in floors]


@router.get("/{floor_id}")
def get_floor(floor_id: int, db: DB, p: CurrentUser) -> FloorDetail:
    ensure_can_view_floor(p, floor_id)
    floor = floor_service.get_floor(db, floor_id)
    cars = car_service.floor_cars(db, p, floor_id)
    return floor_detail(floor, cars_out(db, cars, utcnow()))


@router.get("/{floor_id}/history")
def floor_history(floor_id: int, db: DB, p: CurrentUser) -> list[CarOut]:
    return cars_out(db, car_service.floor_history(db, p, floor_id), utcnow())


@router.patch("/{floor_id}")
def update_capacity(
    floor_id: int, body: FloorCapacityIn, db: DB, p: CurrentUser, background: BackgroundTasks
) -> FloorDetail:
    floor = floor_service.set_capacity(db, p, floor_id, body.capacity)
    db.commit()
    db.refresh(floor)
    cars = car_service.floor_cars(db, p, floor_id)
    detail = floor_detail(floor, cars_out(db, cars, utcnow()))
    background.add_task(hub.publish_floor, floor_id, detail.model_dump(mode="json"))
    return detail
