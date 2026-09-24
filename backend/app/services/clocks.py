"""Os dois relógios do parquímetro (seção 4 da SPEC).

- Prazo: vence quando now > due_at. Nunca pausa.
- Tempo parado: tempo útil desde a última movimentação, descontando intervalos
  com pisca-alerta ligado. Calculado sempre a partir do log de eventos.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Car, CarStatus, Event, EventType

Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class ClockState:
    is_overdue: bool
    stopped_seconds: int
    is_stale: bool
    last_movement_at: datetime | None


def is_overdue(car: Car, now: datetime) -> bool:
    return car.status != CarStatus.CONCLUIDO and now > car.due_at


def business_seconds(start: datetime, end: datetime, tz: ZoneInfo) -> float:
    """Segundos entre start e end que caem em dias úteis (seg-sex) no fuso dado."""
    if end <= start:
        return 0.0
    total = 0.0
    cursor = start.astimezone(tz)
    end_local = end.astimezone(tz)
    while cursor < end_local:
        next_midnight = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), tzinfo=tz)
        segment_end = min(next_midnight, end_local)
        if cursor.weekday() < 5:
            total += (segment_end - cursor).total_seconds()
        cursor = segment_end
    return total


def hazard_intervals(events: Sequence[Event], now: datetime) -> list[Interval]:
    """Intervalos em que o pisca-alerta esteve ligado, reconstruídos a partir do log."""
    intervals: list[Interval] = []
    started: datetime | None = None
    for event in events:
        if event.type == EventType.HAZARD_ON and started is None:
            started = event.timestamp
        elif event.type == EventType.HAZARD_OFF and started is not None:
            intervals.append((started, event.timestamp))
            started = None
    if started is not None:
        intervals.append((started, now))
    return intervals


def subtract_intervals(window: Interval, holes: Iterable[Interval]) -> list[Interval]:
    """Retorna as partes de `window` que não estão cobertas por `holes`."""
    pieces = [window]
    for hole_start, hole_end in holes:
        next_pieces: list[Interval] = []
        for start, end in pieces:
            if hole_end <= start or hole_start >= end:
                next_pieces.append((start, end))
                continue
            if hole_start > start:
                next_pieces.append((start, hole_start))
            if hole_end < end:
                next_pieces.append((hole_end, end))
        pieces = next_pieces
    return pieces


def stopped_seconds(
    events: Sequence[Event], now: datetime, settings: Settings | None = None
) -> tuple[float, datetime | None]:
    """Tempo parado (em segundos úteis) e o instante da última movimentação.

    `events` deve estar em ordem cronológica.
    """
    settings = settings or get_settings()
    ignored = set(settings.stale_ignored_events)
    movements = [e.timestamp for e in events if e.type.value not in ignored]
    if not movements:
        return 0.0, None
    last_movement = max(movements)
    active = subtract_intervals((last_movement, now), hazard_intervals(events, now))
    tz = ZoneInfo(settings.timezone)
    return sum(business_seconds(start, end, tz) for start, end in active), last_movement


def stale_limit_seconds(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    return settings.stale_business_days * 24 * 60 * 60


def clock_state(car: Car, events: Sequence[Event], now: datetime, settings: Settings | None = None) -> ClockState:
    settings = settings or get_settings()
    if car.status == CarStatus.CONCLUIDO:
        return ClockState(False, 0, False, None)
    seconds, last_movement = stopped_seconds(events, now, settings)
    return ClockState(
        is_overdue=is_overdue(car, now),
        stopped_seconds=int(seconds),
        is_stale=seconds > stale_limit_seconds(settings),
        last_movement_at=last_movement,
    )


def clock_states(db: Session, cars: Sequence[Car], now: datetime) -> dict[int, ClockState]:
    """Calcula os relógios de vários carros com uma única consulta de eventos."""
    if not cars:
        return {}
    by_car: dict[int, list[Event]] = {car.id: [] for car in cars}
    rows = db.scalars(select(Event).where(Event.car_id.in_(by_car.keys())).order_by(Event.timestamp, Event.id))
    for event in rows:
        by_car[event.car_id].append(event)
    return {car.id: clock_state(car, by_car[car.id], now) for car in cars}
