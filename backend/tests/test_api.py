"""API REST e WebSocket: isolamento entre andares (seção 12 da SPEC)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Spot
from tests.conftest import PASSWORD


@pytest.fixture
def client() -> Iterator[TestClient]:
    # `with` mantém um único event loop para requisições e WebSockets.
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def token_of(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


@pytest.fixture
def world(db, make_user, make_type, client):
    pedido = make_type("Pedido", "📦")
    nota = make_type("Nota fiscal", "🧾")
    ana = make_user("Ana", floor_capacity=4)
    bruno = make_user("Bruno", floor_capacity=4)
    valet = make_user("Marcos", is_valet=True, valet_types=[pedido])
    manager = make_user("Gestora", is_manager=True)
    return {
        "pedido": pedido,
        "nota": nota,
        "ana": ana,
        "bruno": bruno,
        "ana_floor": ana.floor.id,
        "bruno_floor": bruno.floor.id,
        "h_ana": login(client, ana.email),
        "h_bruno": login(client, bruno.email),
        "h_valet": login(client, valet.email),
        "h_manager": login(client, manager.email),
    }


def spot(db, floor_id: int, position: int) -> int:
    return db.scalar(select(Spot.id).where(Spot.floor_id == floor_id, Spot.position == position))


def create_car(client, headers, type_id: int, effort: str = "carro") -> dict:
    due = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = client.post(
        "/api/cars",
        headers=headers,
        json={"title": "Pedido X", "task_type_id": type_id, "effort": effort, "priority": "alta", "due_at": due},
    )
    assert response.status_code == 201, response.text
    return response.json()


def park(client, db, world, car_id: int, floor_id: int, position: int = 0):
    return client.post(
        f"/api/cars/{car_id}/park",
        headers=world["h_valet"],
        json={"floor_id": floor_id, "spot_id": spot(db, floor_id, position)},
    )


def test_login_rejects_wrong_password(client, world, make_user):
    response = client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "x"})
    assert response.status_code == 401


def test_requires_authentication(client):
    assert client.get("/api/floors").status_code == 401


def test_full_flow(client, db, world):
    car = create_car(client, world["h_ana"], world["pedido"].id)
    assert car["status"] == "patio"
    assert car["plate"] == "ADV-0001"

    response = park(client, db, world, car["id"], world["ana_floor"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "estacionado"

    h = world["h_ana"]
    assert client.post(f"/api/cars/{car['id']}/hazard", headers=h, json={"on": True}).json()["hazard_on"]
    response = client.post(f"/api/cars/{car['id']}/complete", headers=h)
    assert response.json()["status"] == "concluido"
    assert response.json()["spot_ids"] == []

    events = client.get(f"/api/cars/{car['id']}/events", headers=h).json()
    assert [e["type"] for e in events] == ["created", "parked", "hazard_on", "hazard_off", "completed"]
    history = client.get(f"/api/floors/{world['ana_floor']}/history", headers=h).json()
    assert [c["id"] for c in history] == [car["id"]]


def test_business_errors_are_clear(client, db, world):
    truck = create_car(client, world["h_ana"], world["pedido"].id, effort="caminhao")
    response = park(client, db, world, truck["id"], world["ana_floor"], position=3)
    assert response.status_code == 409
    assert response.json()["detail"] == "Caminhão precisa de 2 vagas lado a lado"

    other_type = create_car(client, world["h_ana"], world["nota"].id)
    response = park(client, db, world, other_type["id"], world["ana_floor"])
    assert response.status_code == 403


def test_owner_cannot_access_other_floors_by_any_endpoint(client, db, world):
    h = world["h_ana"]
    other = world["bruno_floor"]
    car = create_car(client, world["h_bruno"], world["pedido"].id)
    park(client, db, world, car["id"], other)

    floors = client.get("/api/floors", headers=h).json()
    assert [f["id"] for f in floors] == [world["ana_floor"]]
    assert client.get(f"/api/floors/{other}", headers=h).status_code == 403
    assert client.get(f"/api/floors/{other}/history", headers=h).status_code == 403
    assert client.get(f"/api/cars/{car['id']}", headers=h).status_code == 404
    assert client.get(f"/api/cars/{car['id']}/events", headers=h).status_code == 404
    assert client.patch(f"/api/cars/{car['id']}", headers=h, json={"title": "x"}).status_code == 404
    assert client.post(f"/api/cars/{car['id']}/hazard", headers=h, json={"on": True}).status_code == 404
    assert client.post(f"/api/cars/{car['id']}/complete", headers=h).status_code == 404
    move_body = {"spot_id": spot(db, other, 1)}
    assert client.post(f"/api/cars/{car['id']}/move", headers=h, json=move_body).status_code == 404
    assert client.post(f"/api/cars/{car['id']}/return", headers=h, json={"reason": "x"}).status_code == 404
    assert client.get("/api/patio", headers=h).status_code == 403
    assert client.get("/api/users", headers=h).status_code == 403


def test_valet_and_manager_see_all_floors(client, world):
    for key in ("h_valet", "h_manager"):
        floors = client.get("/api/floors", headers=world[key]).json()
        assert {f["id"] for f in floors} == {world["ana_floor"], world["bruno_floor"]}


def test_manager_changes_capacity(client, db, world):
    floor = world["ana_floor"]
    response = client.patch(f"/api/floors/{floor}", headers=world["h_manager"], json={"capacity": 7})
    assert response.status_code == 200
    assert len(response.json()["spots"]) == 7
    assert client.patch(f"/api/floors/{floor}", headers=world["h_ana"], json={"capacity": 2}).status_code == 403

    car = create_car(client, world["h_ana"], world["pedido"].id)
    park(client, db, world, car["id"], floor, position=6)
    response = client.patch(f"/api/floors/{floor}", headers=world["h_manager"], json={"capacity": 5})
    assert response.status_code == 409


def test_manager_configures_valet_types(client, db, world):
    car = create_car(client, world["h_ana"], world["nota"].id)
    assert client.get("/api/patio", headers=world["h_valet"]).json() == []
    users = client.get("/api/users", headers=world["h_manager"]).json()
    valet = next(u for u in users if u["name"] == "Marcos")
    response = client.patch(
        f"/api/users/{valet['id']}",
        headers=world["h_manager"],
        json={"valet_type_ids": [world["pedido"].id, world["nota"].id]},
    )
    assert response.status_code == 200
    assert [c["id"] for c in client.get("/api/patio", headers=world["h_valet"]).json()] == [car["id"]]


# --- WebSocket ---------------------------------------------------------------------


def test_websocket_rejects_invalid_token(client):
    with client.websocket_connect("/ws?token=invalido") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_owner_cannot_subscribe_to_other_floor(client, world):
    with client.websocket_connect(f"/ws?token={token_of(world['h_ana'])}") as ws:
        ws.send_json({"action": "subscribe", "channel": f"floor:{world['bruno_floor']}"})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"action": "subscribe", "channel": "patio"})
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"action": "subscribe", "channel": f"floor:{world['ana_floor']}"})
        assert ws.receive_json() == {"type": "subscribed", "channel": f"floor:{world['ana_floor']}"}


def test_owner_receives_only_own_floor_over_websocket(client, db, world):
    other_car = create_car(client, world["h_bruno"], world["pedido"].id)
    own_car = create_car(client, world["h_ana"], world["pedido"].id)

    with client.websocket_connect(f"/ws?token={token_of(world['h_ana'])}") as ws:
        ws.send_json({"action": "subscribe", "channel": f"floor:{world['ana_floor']}"})
        ws.send_json({"action": "subscribe", "channel": f"floor:{world['bruno_floor']}"})
        assert ws.receive_json()["type"] == "subscribed"
        assert ws.receive_json()["type"] == "error"

        # Movimentação no andar do Bruno não pode chegar para a Ana...
        assert park(client, db, world, other_car["id"], world["bruno_floor"]).status_code == 200
        # ...então a próxima mensagem que ela recebe é a do próprio andar.
        assert park(client, db, world, own_car["id"], world["ana_floor"]).status_code == 200
        message = ws.receive_json()
        assert message["type"] == "car_upserted"
        assert message["event"] == "parked"
        assert message["channel"] == f"floor:{world['ana_floor']}"
        assert message["car"]["id"] == own_car["id"]


def test_valet_patio_channel_filters_by_type(client, db, world):
    with client.websocket_connect(f"/ws?token={token_of(world['h_valet'])}") as ws:
        ws.send_json({"action": "subscribe", "channel": "patio"})
        assert ws.receive_json()["type"] == "subscribed"
        create_car(client, world["h_ana"], world["nota"].id)  # fora da responsabilidade
        pedido = create_car(client, world["h_ana"], world["pedido"].id)
        message = ws.receive_json()
        assert message["type"] == "car_upserted"
        assert message["car"]["id"] == pedido["id"]


def test_parking_moves_car_between_channels(client, db, world):
    car = create_car(client, world["h_ana"], world["pedido"].id)
    with client.websocket_connect(f"/ws?token={token_of(world['h_manager'])}") as ws:
        ws.send_json({"action": "subscribe", "channel": "patio"})
        ws.send_json({"action": "subscribe", "channel": f"floor:{world['ana_floor']}"})
        ws.receive_json()
        ws.receive_json()
        park(client, db, world, car["id"], world["ana_floor"])
        removed = ws.receive_json()
        arrived = ws.receive_json()
        assert (removed["type"], removed["channel"], removed["car_id"]) == ("car_removed", "patio", car["id"])
        assert (arrived["type"], arrived["channel"]) == ("car_upserted", f"floor:{world['ana_floor']}")

        client.post(f"/api/cars/{car['id']}/complete", headers=world["h_ana"])
        left = ws.receive_json()
        assert (left["type"], left["event"]) == ("car_removed", "completed")
