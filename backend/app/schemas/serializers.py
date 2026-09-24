"""Conversão de modelos em schemas de saída (usada pela API e pelo WebSocket)."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Car, Event, Floor, User
from app.schemas.car import ActorOut, CarOut, ClockOut, EventOut, TaskTypeOut
from app.schemas.floor import FloorDetail, FloorSummary, OwnerOut, SpotOut
from app.schemas.user import UserOut
from app.services.clocks import ClockState, clock_states, stale_limit_seconds


def car_out(car: Car, clock: ClockState, now: datetime) -> CarOut:
    spots = car.spots
    return CarOut(
        id=car.id,
        plate=car.plate,
        title=car.title,
        description=car.description,
        task_type=TaskTypeOut(id=car.task_type.id, name=car.task_type.name, icon=car.task_type.icon),
        effort=car.effort,
        priority=car.priority,
        due_at=car.due_at,
        status=car.status,
        hazard_on=car.hazard_on,
        floor_id=car.floor_id,
        spot_ids=[s.id for s in spots],
        spot_positions=[s.position for s in spots],
        created_by=car.created_by,
        created_at=car.created_at,
        clock=ClockOut(
            is_overdue=clock.is_overdue,
            is_stale=clock.is_stale,
            stopped_seconds=clock.stopped_seconds,
            stale_limit_seconds=stale_limit_seconds(),
            last_movement_at=clock.last_movement_at,
            computed_at=now,
        ),
    )


def cars_out(db: Session, cars: Sequence[Car], now: datetime) -> list[CarOut]:
    clocks = clock_states(db, cars, now)
    return [car_out(car, clocks[car.id], now) for car in cars]


def floor_summary(floor: Floor, occupied: int) -> FloorSummary:
    return FloorSummary(
        id=floor.id,
        position=floor.position,
        capacity=floor.capacity,
        occupied=occupied,
        owner=OwnerOut(id=floor.owner.id, name=floor.owner.name),
    )


def floor_detail(floor: Floor, cars: list[CarOut]) -> FloorDetail:
    occupied = sum(len(c.spot_ids) for c in cars)
    return FloorDetail(
        **floor_summary(floor, occupied).model_dump(),
        spots=[SpotOut(id=s.id, position=s.position, row=s.row, column=s.column) for s in floor.spots],
        cars=cars,
    )


def event_out(event: Event) -> EventOut:
    return EventOut(
        id=event.id,
        type=event.type,
        actor=ActorOut(id=event.actor.id, name=event.actor.name),
        timestamp=event.timestamp,
        payload=event.payload,
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_manager=user.is_manager,
        is_valet=user.is_valet,
        floor_id=user.floor.id if user.floor else None,
        valet_type_ids=[t.id for t in user.valet_types],
    )
