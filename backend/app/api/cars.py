"""Rotas de veículos. Só orquestram: regra de negócio fica em services/cars.py."""

from fastapi import APIRouter, BackgroundTasks

from app.api.deps import DB, CurrentUser, car_broadcast
from app.schemas.car import (
    CarCreate,
    CarOut,
    CarUpdate,
    EventOut,
    HazardIn,
    MoveIn,
    ParkIn,
    ReturnIn,
)
from app.schemas.serializers import cars_out, event_out
from app.services import cars as car_service
from app.services.cars import CarChange, utcnow
from app.ws.hub import hub

router = APIRouter(tags=["cars"])


def _finish(db: DB, background: BackgroundTasks, change: CarChange | None, car_id: int, p: CurrentUser) -> CarOut:
    """Commit + agenda o broadcast (roda depois da resposta) + devolve o carro atualizado."""
    db.commit()
    if change is None:  # nada mudou: sem evento e sem broadcast
        car = car_service.get_visible_car(db, p, car_id)
        return cars_out(db, [car], utcnow())[0]
    broadcast = car_broadcast(db, change)
    background.add_task(hub.publish_car, broadcast)
    return CarOut.model_validate(broadcast.car)


@router.get("/patio")
def patio(db: DB, p: CurrentUser) -> list[CarOut]:
    return cars_out(db, car_service.patio_cars(db, p), utcnow())


@router.post("/cars", status_code=201)
def create_car(body: CarCreate, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.create_car(db, p, **body.model_dump())
    db.commit()
    broadcast = car_broadcast(db, change)
    background.add_task(hub.publish_car, broadcast)
    # O criador recebe o carro de volta mesmo sem acesso ao pátio (é a confirmação da cancela).
    return CarOut.model_validate(broadcast.car)


@router.get("/cars/{car_id}")
def get_car(car_id: int, db: DB, p: CurrentUser) -> CarOut:
    car = car_service.get_visible_car(db, p, car_id)
    return cars_out(db, [car], utcnow())[0]


@router.get("/cars/{car_id}/events")
def get_events(car_id: int, db: DB, p: CurrentUser) -> list[EventOut]:
    return [event_out(e) for e in car_service.car_events(db, p, car_id)]


@router.patch("/cars/{car_id}")
def update_car(car_id: int, body: CarUpdate, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.update_car(db, p, car_id, body.model_dump(exclude_unset=True))
    return _finish(db, background, change, car_id, p)


@router.post("/cars/{car_id}/park")
def park(car_id: int, body: ParkIn, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.park_car(db, p, car_id, body.floor_id, body.spot_id)
    return _finish(db, background, change, car_id, p)


@router.post("/cars/{car_id}/move")
def move(car_id: int, body: MoveIn, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.move_car(db, p, car_id, body.spot_id)
    return _finish(db, background, change, car_id, p)


@router.post("/cars/{car_id}/hazard")
def hazard(car_id: int, body: HazardIn, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.set_hazard(db, p, car_id, body.on)
    return _finish(db, background, change, car_id, p)


@router.post("/cars/{car_id}/complete")
def complete(car_id: int, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.complete_car(db, p, car_id)
    return _finish(db, background, change, car_id, p)


@router.post("/cars/{car_id}/return")
def return_to_patio(car_id: int, body: ReturnIn, db: DB, p: CurrentUser, background: BackgroundTasks) -> CarOut:
    change = car_service.return_to_patio(db, p, car_id, body.reason)
    return _finish(db, background, change, car_id, p)
