"""Regras de negócio dos veículos (tarefas).

Toda mutação em Car grava um Event na mesma transação. As funções só fazem flush;
quem chama (a rota) é responsável pelo commit.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Car,
    CarSpot,
    CarStatus,
    Effort,
    Event,
    EventType,
    Floor,
    Priority,
    Spot,
    TaskType,
    plate_seq,
)
from app.services.errors import Conflict, Forbidden, InvalidInput, NotFound
from app.services.floors import get_floor, occupied_spot_ids
from app.services.permissions import (
    Principal,
    can_park,
    can_return_to_patio,
    can_view_patio_car,
    ensure_can_view_car,
    ensure_can_view_floor,
    ensure_can_view_patio,
    ensure_floor_owner,
)

FLOOR_FULL = "Andar lotado"
TRUCK_NEEDS_TWO = "Caminhão precisa de 2 vagas lado a lado"
SPOT_TAKEN = "Vaga ocupada"


@dataclass
class CarChange:
    """Descreve o que mudou, para o WebSocket saber para quem transmitir."""

    car: Car
    event: Event
    previous_status: CarStatus | None
    previous_floor_id: int | None


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def record_event(
    db: Session,
    car: Car,
    event_type: EventType,
    actor_id: int,
    now: datetime,
    payload: dict[str, Any] | None = None,
) -> Event:
    event = Event(car=car, type=event_type, actor_id=actor_id, timestamp=now, payload=payload or {})
    db.add(event)
    return event


def _get_car(db: Session, car_id: int, *, lock: bool = False) -> Car:
    stmt = select(Car).where(Car.id == car_id)
    if lock:
        stmt = stmt.with_for_update(of=Car)
    car = db.scalar(stmt)
    if car is None:
        raise NotFound("Veículo não encontrado")
    return car


def get_visible_car(db: Session, p: Principal, car_id: int) -> Car:
    car = _get_car(db, car_id)
    ensure_can_view_car(p, car)
    return car


def _get_task_type(db: Session, task_type_id: int) -> TaskType:
    task_type = db.get(TaskType, task_type_id)
    if task_type is None:
        raise InvalidInput("Tipo de tarefa inválido")
    return task_type


def _spot_positions(car: Car) -> list[int]:
    return [spot.position for spot in car.spots]


# --- consultas ------------------------------------------------------------------


def patio_cars(db: Session, p: Principal) -> list[Car]:
    ensure_can_view_patio(p)
    cars = db.scalars(select(Car).where(Car.status == CarStatus.PATIO).order_by(Car.created_at, Car.id))
    return [car for car in cars if can_view_patio_car(p, car.task_type_id)]


def floor_cars(db: Session, p: Principal, floor_id: int) -> list[Car]:
    ensure_can_view_floor(p, floor_id)
    return list(
        db.scalars(select(Car).where(Car.floor_id == floor_id, Car.status == CarStatus.ESTACIONADO).order_by(Car.id))
    )


def floor_history(db: Session, p: Principal, floor_id: int, limit: int = 50) -> list[Car]:
    ensure_can_view_floor(p, floor_id)
    return list(
        db.scalars(
            select(Car)
            .where(Car.floor_id == floor_id, Car.status == CarStatus.CONCLUIDO)
            .order_by(Car.id.desc())
            .limit(limit)
        )
    )


def car_events(db: Session, p: Principal, car_id: int) -> list[Event]:
    car = get_visible_car(db, p, car_id)
    return list(car.events)


# --- cancela --------------------------------------------------------------------


def next_plate(db: Session) -> str:
    number = db.scalar(plate_seq.next_value())
    return f"{get_settings().plate_prefix}-{number:04d}"


def create_car(
    db: Session,
    p: Principal,
    *,
    title: str,
    description: str,
    task_type_id: int,
    effort: Effort,
    priority: Priority,
    due_at: datetime,
    now: datetime | None = None,
) -> CarChange:
    """Cancela: qualquer usuário cria; o carro nasce no pátio."""
    now = now or utcnow()
    if not title.strip():
        raise InvalidInput("Informe um título")
    _get_task_type(db, task_type_id)
    car = Car(
        plate=next_plate(db),
        title=title.strip(),
        description=description.strip(),
        task_type_id=task_type_id,
        effort=effort,
        priority=priority,
        due_at=_aware(due_at),
        status=CarStatus.PATIO,
        hazard_on=False,
        created_by=p.user_id,
        created_at=now,
    )
    db.add(car)
    event = record_event(db, car, EventType.CREATED, p.user_id, now)
    db.flush()
    db.refresh(car)
    return CarChange(car, event, None, None)


# --- vagas ----------------------------------------------------------------------


def _target_spots(db: Session, floor: Floor, spot_id: int, effort: Effort) -> list[Spot]:
    """Vagas que o veículo ocuparia começando por `spot_id` (caminhão: ela + a da direita)."""
    spot = db.get(Spot, spot_id)
    if spot is None or spot.floor_id != floor.id:
        raise InvalidInput("Vaga não pertence a este andar")
    if effort.spots_needed == 1:
        return [spot]
    neighbor = db.scalar(
        select(Spot).where(Spot.floor_id == floor.id, Spot.row == spot.row, Spot.column == spot.column + 1)
    )
    if neighbor is None:
        raise Conflict(TRUCK_NEEDS_TWO)
    return [spot, neighbor]


def _ensure_free(targets: list[Spot], occupied: set[int], effort: Effort) -> None:
    if any(spot.id in occupied for spot in targets):
        raise Conflict(TRUCK_NEEDS_TWO if effort == Effort.CAMINHAO else SPOT_TAKEN)


def _assign_spots(db: Session, car: Car, spots: list[Spot]) -> None:
    car.car_spots.clear()
    db.flush()
    car.car_spots.extend(CarSpot(spot=spot) for spot in spots)
    try:
        db.flush()
    except IntegrityError as exc:  # corrida: outra pessoa pegou a vaga no mesmo instante
        raise Conflict(SPOT_TAKEN) from exc


def park_car(
    db: Session,
    p: Principal,
    car_id: int,
    floor_id: int,
    spot_id: int,
    now: datetime | None = None,
) -> CarChange:
    """Manobrista estaciona um carro do pátio num andar."""
    now = now or utcnow()
    car = _get_car(db, car_id, lock=True)
    if car.status != CarStatus.PATIO:
        ensure_can_view_car(p, car)
        raise Conflict("Este veículo não está no pátio")
    if not can_park(p, car.task_type_id):
        raise Forbidden("Você não é responsável por este tipo de tarefa")

    # Trava o andar para que duas manobras simultâneas não furem o limite.
    floor = get_floor(db, floor_id, lock=True)
    occupied = occupied_spot_ids(db, floor.id)
    if len(occupied) >= floor.capacity:
        raise Conflict(FLOOR_FULL)
    targets = _target_spots(db, floor, spot_id, car.effort)
    _ensure_free(targets, occupied, car.effort)

    _assign_spots(db, car, targets)
    car.status = CarStatus.ESTACIONADO
    car.floor_id = floor.id
    event = record_event(
        db,
        car,
        EventType.PARKED,
        p.user_id,
        now,
        {"floor_id": floor.id, "spots": [s.position for s in targets]},
    )
    db.flush()
    return CarChange(car, event, CarStatus.PATIO, None)


def _get_owned_parked_car(db: Session, p: Principal, car_id: int) -> Car:
    car = _get_car(db, car_id, lock=True)
    ensure_can_view_car(p, car)
    if car.status != CarStatus.ESTACIONADO:
        raise Conflict("Este veículo não está estacionado")
    ensure_floor_owner(p, car)
    return car


def move_car(db: Session, p: Principal, car_id: int, spot_id: int, now: datetime | None = None) -> CarChange | None:
    """Dono do andar troca o carro de vaga dentro do próprio andar."""
    now = now or utcnow()
    car = _get_owned_parked_car(db, p, car_id)
    floor = get_floor(db, car.floor_id, lock=True)  # type: ignore[arg-type]
    targets = _target_spots(db, floor, spot_id, car.effort)
    before = _spot_positions(car)
    after = [s.position for s in targets]
    if before == after:
        return None
    own = {s.id for s in car.spots}
    _ensure_free(targets, occupied_spot_ids(db, floor.id) - own, car.effort)
    _assign_spots(db, car, targets)
    event = record_event(db, car, EventType.MOVED_SPOT, p.user_id, now, {"before": before, "after": after})
    db.flush()
    return CarChange(car, event, car.status, car.floor_id)


# --- trabalho no andar ------------------------------------------------------------

EDITABLE_FIELDS = ("title", "description", "task_type_id", "effort", "priority", "due_at")


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def update_car(
    db: Session, p: Principal, car_id: int, changes: dict[str, Any], now: datetime | None = None
) -> CarChange | None:
    now = now or utcnow()
    car = _get_owned_parked_car(db, p, car_id)
    normalized: dict[str, Any] = {}
    diff: dict[str, dict[str, Any]] = {}
    for field, value in changes.items():
        if field not in EDITABLE_FIELDS or value is None:
            continue
        if field == "due_at":
            value = _aware(value)
        elif field in ("title", "description"):
            value = value.strip()
            if field == "title" and not value:
                raise InvalidInput("Informe um título")
        elif field == "task_type_id":
            _get_task_type(db, value)
        elif field == "effort":
            value = Effort(value)
        elif field == "priority":
            value = Priority(value)
        current = getattr(car, field)
        if current != value:
            normalized[field] = value
            diff[field] = {"before": _json_value(current), "after": _json_value(value)}

    if not diff:
        return None

    new_effort: Effort | None = normalized.get("effort")
    if new_effort is not None and new_effort.spots_needed != car.effort.spots_needed:
        # Mudar de/para caminhão muda a quantidade de vagas ocupadas.
        floor = get_floor(db, car.floor_id, lock=True)  # type: ignore[arg-type]
        targets = _target_spots(db, floor, car.spots[0].id, new_effort)
        own = {s.id for s in car.spots}
        _ensure_free(targets, occupied_spot_ids(db, floor.id) - own, new_effort)
        _assign_spots(db, car, targets)

    for field, value in normalized.items():
        setattr(car, field, value)
    event = record_event(db, car, EventType.UPDATED, p.user_id, now, diff)
    db.flush()
    db.refresh(car)
    return CarChange(car, event, car.status, car.floor_id)


def set_hazard(db: Session, p: Principal, car_id: int, on: bool, now: datetime | None = None) -> CarChange | None:
    now = now or utcnow()
    car = _get_owned_parked_car(db, p, car_id)
    if car.hazard_on == on:
        return None
    car.hazard_on = on
    event = record_event(db, car, EventType.HAZARD_ON if on else EventType.HAZARD_OFF, p.user_id, now)
    db.flush()
    return CarChange(car, event, car.status, car.floor_id)


def complete_car(db: Session, p: Principal, car_id: int, now: datetime | None = None) -> CarChange:
    """Saída: tira o carro da vaga e manda para o histórico."""
    now = now or utcnow()
    car = _get_owned_parked_car(db, p, car_id)
    positions = _spot_positions(car)
    car.car_spots.clear()
    if car.hazard_on:
        car.hazard_on = False
        record_event(db, car, EventType.HAZARD_OFF, p.user_id, now)
    car.status = CarStatus.CONCLUIDO
    # floor_id é mantido: indica em que andar a tarefa foi concluída (histórico).
    event = record_event(db, car, EventType.COMPLETED, p.user_id, now, {"spots": positions})
    db.flush()
    return CarChange(car, event, CarStatus.ESTACIONADO, car.floor_id)


def return_to_patio(db: Session, p: Principal, car_id: int, reason: str, now: datetime | None = None) -> CarChange:
    now = now or utcnow()
    car = _get_car(db, car_id, lock=True)
    ensure_can_view_car(p, car)
    if car.status != CarStatus.ESTACIONADO:
        raise Conflict("Este veículo não está estacionado")
    if not can_return_to_patio(p, car):
        raise Forbidden("Apenas o dono do andar ou o gestor pode devolver ao pátio")
    if not reason.strip():
        raise InvalidInput("Informe o motivo da devolução")
    previous_floor_id = car.floor_id
    positions = _spot_positions(car)
    car.car_spots.clear()
    if car.hazard_on:
        # O pisca-alerta só é controlado no andar; ao voltar ao pátio ele é desligado.
        car.hazard_on = False
        record_event(db, car, EventType.HAZARD_OFF, p.user_id, now)
    car.status = CarStatus.PATIO
    car.floor_id = None
    event = record_event(
        db,
        car,
        EventType.RETURNED_TO_PATIO,
        p.user_id,
        now,
        {"reason": reason.strip(), "floor_id": previous_floor_id, "spots": positions},
    )
    db.flush()
    return CarChange(car, event, CarStatus.ESTACIONADO, previous_floor_id)
