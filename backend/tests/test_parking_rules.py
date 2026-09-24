"""Critérios de aceite de estacionamento (seção 12 da SPEC)."""

import pytest
from sqlalchemy import select

from app.models import Car, CarStatus, Effort, Event, EventType, Floor, Spot
from app.services import cars as car_service
from app.services.errors import Conflict, Forbidden
from tests.conftest import MONDAY


def spot_id(db, floor: Floor, position: int) -> int:
    return db.scalar(select(Spot.id).where(Spot.floor_id == floor.id, Spot.position == position))


@pytest.fixture
def setup(db, make_user, make_type):
    pedido = make_type("Pedido", "📦")
    nota = make_type("Nota fiscal", "🧾")
    valet = make_user("Manobrista", is_valet=True, valet_types=[pedido])
    owner = make_user("Dona", floor_capacity=3)
    return {"pedido": pedido, "nota": nota, "valet": valet, "owner": owner, "floor": owner.floor}


def test_valet_cannot_park_type_outside_responsibility(db, setup, make_car, principal):
    car_id = make_car(setup["owner"], setup["nota"])
    with pytest.raises(Forbidden):
        car_service.park_car(db, principal(setup["valet"]), car_id, setup["floor"].id, spot_id(db, setup["floor"], 0))


def test_valet_parks_type_under_responsibility(db, setup, make_car, principal):
    car_id = make_car(setup["owner"], setup["pedido"])
    change = car_service.park_car(
        db, principal(setup["valet"]), car_id, setup["floor"].id, spot_id(db, setup["floor"], 0)
    )
    db.commit()
    assert change.car.status == CarStatus.ESTACIONADO
    assert change.car.floor_id == setup["floor"].id
    assert [s.position for s in change.car.spots] == [0]
    assert change.event.type == EventType.PARKED


def test_valet_does_not_see_other_types_in_patio(db, setup, make_car, principal):
    make_car(setup["owner"], setup["pedido"])
    make_car(setup["owner"], setup["nota"])
    visible = car_service.patio_cars(db, principal(setup["valet"]))
    assert [c.task_type_id for c in visible] == [setup["pedido"].id]


def test_owner_cannot_see_patio(db, setup, principal):
    with pytest.raises(Forbidden):
        car_service.patio_cars(db, principal(setup["owner"]))


def test_full_floor_rejects_new_cars(db, setup, make_car, principal):
    floor = setup["floor"]
    valet = principal(setup["valet"])
    for position in range(3):
        car_id = make_car(setup["owner"], setup["pedido"], effort=Effort.MOTO)
        car_service.park_car(db, valet, car_id, floor.id, spot_id(db, floor, position))
        db.commit()

    extra = make_car(setup["owner"], setup["pedido"], effort=Effort.MOTO)
    with pytest.raises(Conflict, match="Andar lotado"):
        car_service.park_car(db, valet, extra, floor.id, spot_id(db, floor, 0))


def test_occupied_spot_is_rejected(db, setup, make_car, principal):
    floor = setup["floor"]
    valet = principal(setup["valet"])
    first = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, valet, first, floor.id, spot_id(db, floor, 1))
    db.commit()
    second = make_car(setup["owner"], setup["pedido"])
    with pytest.raises(Conflict, match="Vaga ocupada"):
        car_service.park_car(db, valet, second, floor.id, spot_id(db, floor, 1))


def test_truck_parks_in_two_contiguous_free_spots(db, setup, make_car, principal):
    floor = setup["floor"]
    truck = make_car(setup["owner"], setup["pedido"], effort=Effort.CAMINHAO)
    change = car_service.park_car(db, principal(setup["valet"]), truck, floor.id, spot_id(db, floor, 0))
    db.commit()
    assert [s.position for s in change.car.spots] == [0, 1]


def test_truck_rejected_when_neighbor_spot_is_taken(db, setup, make_car, principal):
    floor = setup["floor"]
    valet = principal(setup["valet"])
    moto = make_car(setup["owner"], setup["pedido"], effort=Effort.MOTO)
    car_service.park_car(db, valet, moto, floor.id, spot_id(db, floor, 1))
    db.commit()

    truck = make_car(setup["owner"], setup["pedido"], effort=Effort.CAMINHAO)
    # Vagas 0 e 2 estão livres, mas não são vizinhas.
    with pytest.raises(Conflict, match="Caminhão precisa de 2 vagas lado a lado"):
        car_service.park_car(db, valet, truck, floor.id, spot_id(db, floor, 0))


def test_truck_rejected_at_end_of_row(db, setup, make_car, principal):
    floor = setup["floor"]
    truck = make_car(setup["owner"], setup["pedido"], effort=Effort.CAMINHAO)
    # A vaga 2 é a última do andar (capacidade 3): não há vizinha à direita.
    with pytest.raises(Conflict, match="Caminhão precisa de 2 vagas lado a lado"):
        car_service.park_car(db, principal(setup["valet"]), truck, floor.id, spot_id(db, floor, 2))


def test_truck_does_not_span_rows(db, make_user, make_type, make_car, principal):
    pedido = make_type()
    manager = make_user(is_manager=True)
    owner = make_user(floor_capacity=12)  # 2 fileiras de 6
    floor = owner.floor
    truck = make_car(owner, pedido, effort=Effort.CAMINHAO)
    with pytest.raises(Conflict, match="lado a lado"):
        car_service.park_car(db, principal(manager), truck, floor.id, spot_id(db, floor, 5))


def test_owner_moves_car_within_own_floor(db, setup, make_car, principal):
    floor = setup["floor"]
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()

    change = car_service.move_car(db, principal(setup["owner"]), car_id, spot_id(db, floor, 2))
    db.commit()
    assert change is not None
    assert [s.position for s in change.car.spots] == [2]
    assert change.event.payload == {"before": [0], "after": [2]}


def test_valet_cannot_move_car_between_spots(db, setup, make_car, principal):
    floor = setup["floor"]
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()
    with pytest.raises(Forbidden):
        car_service.move_car(db, principal(setup["valet"]), car_id, spot_id(db, floor, 2))


def test_complete_removes_car_from_spot_and_records_event(db, setup, make_car, principal):
    floor = setup["floor"]
    car_id = make_car(setup["owner"], setup["pedido"], effort=Effort.CAMINHAO)
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()

    car_service.complete_car(db, principal(setup["owner"]), car_id)
    db.commit()
    db.expire_all()

    car = db.get(Car, car_id)
    assert car.status == CarStatus.CONCLUIDO
    assert car.spots == []
    events = db.scalars(select(Event.type).where(Event.car_id == car_id).order_by(Event.id)).all()
    assert events[-1] == EventType.COMPLETED
    # As vagas ficaram livres para outro veículo.
    other = make_car(setup["owner"], setup["pedido"], effort=Effort.CAMINHAO)
    car_service.park_car(db, principal(setup["valet"]), other, floor.id, spot_id(db, floor, 0))


def test_only_owner_completes(db, setup, make_user, make_car, principal):
    floor = setup["floor"]
    manager = make_user(is_manager=True)
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()
    with pytest.raises(Forbidden):
        car_service.complete_car(db, principal(manager), car_id)


def test_return_to_patio_requires_reason_and_frees_spot(db, setup, make_car, principal):
    floor = setup["floor"]
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()

    change = car_service.return_to_patio(db, principal(setup["owner"]), car_id, "Não é do meu escopo")
    db.commit()
    assert change.car.status == CarStatus.PATIO
    assert change.car.floor_id is None
    assert change.car.spots == []
    assert change.event.payload["reason"] == "Não é do meu escopo"
    assert change.previous_floor_id == floor.id


def test_manager_can_return_but_valet_cannot(db, setup, make_user, make_car, principal):
    floor = setup["floor"]
    manager = make_user(is_manager=True)
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()
    with pytest.raises(Forbidden):
        car_service.return_to_patio(db, principal(setup["valet"]), car_id, "motivo")
    car_service.return_to_patio(db, principal(manager), car_id, "motivo")


def test_every_mutation_records_an_event(db, setup, make_car, principal):
    floor = setup["floor"]
    owner = principal(setup["owner"])
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    car_service.move_car(db, owner, car_id, spot_id(db, floor, 1))
    car_service.update_car(db, owner, car_id, {"title": "Novo título"})
    car_service.set_hazard(db, owner, car_id, True)
    car_service.set_hazard(db, owner, car_id, False)
    car_service.return_to_patio(db, owner, car_id, "motivo")
    db.commit()
    types = db.scalars(select(Event.type).where(Event.car_id == car_id).order_by(Event.id)).all()
    assert types == [
        EventType.CREATED,
        EventType.PARKED,
        EventType.MOVED_SPOT,
        EventType.UPDATED,
        EventType.HAZARD_ON,
        EventType.HAZARD_OFF,
        EventType.RETURNED_TO_PATIO,
    ]


def test_changing_effort_to_truck_claims_neighbor_spot(db, setup, make_car, principal):
    floor = setup["floor"]
    car_id = make_car(setup["owner"], setup["pedido"])
    car_service.park_car(db, principal(setup["valet"]), car_id, floor.id, spot_id(db, floor, 0))
    db.commit()
    change = car_service.update_car(db, principal(setup["owner"]), car_id, {"effort": Effort.CAMINHAO})
    db.commit()
    assert [s.position for s in change.car.spots] == [0, 1]


def test_events_table_is_append_only(db, setup, make_car):
    make_car(setup["owner"], setup["pedido"], now=MONDAY)
    with pytest.raises(Exception, match="append-only"):
        db.execute(Event.__table__.update().values(payload={}))
    db.rollback()
