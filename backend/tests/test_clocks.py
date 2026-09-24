"""Relógios do parquímetro: prazo e tempo parado (seção 4 da SPEC)."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Car, Effort, Spot
from app.services import cars as car_service
from app.services.clocks import clock_states, stale_limit_seconds
from tests.conftest import MONDAY

HOUR = 3600


@pytest.fixture
def parked(db, make_user, make_type, make_car, principal):
    """Carro estacionado na segunda às 10h (horário de São Paulo)."""
    pedido = make_type()
    manager = make_user(is_manager=True)
    owner = make_user(floor_capacity=4)
    car_id = make_car(owner, pedido, effort=Effort.CARRO, due_at=MONDAY + timedelta(hours=3))
    spot = db.scalar(select(Spot.id).where(Spot.floor_id == owner.floor.id, Spot.position == 0))
    car_service.park_car(db, principal(manager), car_id, owner.floor.id, spot, now=MONDAY)
    db.commit()
    return {"car_id": car_id, "owner": principal(owner)}


def clock(db, car_id: int, now):
    db.expire_all()
    car = db.get(Car, car_id)
    return clock_states(db, [car], now)[car_id]


def test_stopped_time_discounts_hazard_intervals(db, parked):
    car_id, owner = parked["car_id"], parked["owner"]
    car_service.set_hazard(db, owner, car_id, True, now=MONDAY + timedelta(hours=2))
    car_service.set_hazard(db, owner, car_id, False, now=MONDAY + timedelta(hours=26))
    db.commit()

    # 48h desde o estacionamento, 24h delas com pisca-alerta ligado.
    state = clock(db, car_id, MONDAY + timedelta(hours=48))
    assert state.stopped_seconds == 24 * HOUR
    # Ligar/desligar o pisca-alerta não conta como movimentação.
    assert state.last_movement_at == MONDAY


def test_stopped_time_is_frozen_while_hazard_is_on(db, parked):
    car_id, owner = parked["car_id"], parked["owner"]
    car_service.set_hazard(db, owner, car_id, True, now=MONDAY + timedelta(hours=1))
    db.commit()
    assert clock(db, car_id, MONDAY + timedelta(hours=1)).stopped_seconds == HOUR
    assert clock(db, car_id, MONDAY + timedelta(hours=30)).stopped_seconds == HOUR


def test_deadline_keeps_running_with_hazard_on(db, parked):
    car_id, owner = parked["car_id"], parked["owner"]
    car_service.set_hazard(db, owner, car_id, True, now=MONDAY + timedelta(hours=1))
    db.commit()
    # Prazo era segunda 13h; com o pisca-alerta ligado desde 11h, às 14h continua vencido.
    assert clock(db, car_id, MONDAY + timedelta(hours=2)).is_overdue is False
    assert clock(db, car_id, MONDAY + timedelta(hours=4)).is_overdue is True


def test_movement_resets_stopped_time(db, parked):
    car_id, owner = parked["car_id"], parked["owner"]
    later = MONDAY + timedelta(hours=5)
    spot = db.scalar(select(Spot.id).where(Spot.floor_id == owner.owned_floor_id, Spot.position == 2))
    car_service.move_car(db, owner, car_id, spot, now=later)
    db.commit()
    assert clock(db, car_id, later + timedelta(hours=1)).stopped_seconds == HOUR


def test_stale_after_three_business_days_skipping_weekend(db, parked):
    car_id = parked["car_id"]
    assert stale_limit_seconds() == 3 * 24 * HOUR
    # Segunda 10h -> quinta 10h = exatamente 3 dias úteis: ainda não venceu.
    assert clock(db, car_id, MONDAY + timedelta(days=3)).is_stale is False
    assert clock(db, car_id, MONDAY + timedelta(days=3, minutes=1)).is_stale is True


def test_weekend_does_not_count(db, make_user, make_type, make_car, principal):
    pedido = make_type()
    friday = MONDAY - timedelta(days=3)
    owner = make_user(floor_capacity=2)
    car_id = make_car(owner, pedido, now=friday)
    # Sexta 10h -> segunda 10h: 14h de sexta + 10h de segunda. Sábado e domingo não contam.
    state = clock(db, car_id, MONDAY)
    assert state.stopped_seconds == 24 * HOUR
