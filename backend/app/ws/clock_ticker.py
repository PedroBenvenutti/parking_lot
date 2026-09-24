"""Checagem periódica dos relógios.

Prazo e tempo parado vencem com a passagem do tempo, sem nenhum evento novo.
A cada `clock_tick_seconds` recalculamos os carros ativos e transmitimos os
que mudaram de estado (venceu o prazo, ficou parado, etc.).
"""

import asyncio
import logging

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import SessionLocal
from app.models import Car, CarStatus
from app.schemas.serializers import cars_out
from app.services.cars import utcnow
from app.ws.hub import CarBroadcast, hub

log = logging.getLogger(__name__)

ClockFlags = tuple[bool, bool]


def _snapshot() -> list[tuple[ClockFlags, CarBroadcast]]:
    now = utcnow()
    with SessionLocal() as db:
        cars = list(db.scalars(select(Car).where(Car.status != CarStatus.CONCLUIDO)))
        result = []
        for car, out in zip(cars, cars_out(db, cars, now), strict=True):
            flags = (out.clock.is_overdue, out.clock.is_stale)
            broadcast = CarBroadcast(
                car=out.model_dump(mode="json"),
                task_type_id=car.task_type_id,
                event_type="clock",
                status=car.status,
                floor_id=car.floor_id,
                previous_status=car.status,
                previous_floor_id=car.floor_id,
            )
            result.append((flags, broadcast))
        return result


async def run_clock_ticker() -> None:
    interval = get_settings().clock_tick_seconds
    known: dict[int, ClockFlags] = {}
    while True:
        try:
            snapshot = await run_in_threadpool(_snapshot)
            for flags, broadcast in snapshot:
                car_id = broadcast.car["id"]
                if car_id in known and known[car_id] != flags:
                    await hub.publish_car(broadcast)
                known[car_id] = flags
        except Exception:
            log.exception("Clock ticker failed")
        await asyncio.sleep(interval)
