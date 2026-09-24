"""Distribuição de mensagens em tempo real por canal (um por andar + o pátio).

Cada conexão guarda o `Principal` do usuário. Antes de enviar qualquer mensagem,
o hub checa a permissão com as mesmas funções usadas pela API: o dono de um andar
nunca recebe dados de outro andar, mesmo que tente se inscrever no canal.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.models import CarStatus
from app.services.permissions import (
    Principal,
    can_view_floor,
    can_view_patio,
    can_view_patio_car,
)

log = logging.getLogger(__name__)

PATIO = "patio"


def floor_channel(floor_id: int) -> str:
    return f"floor:{floor_id}"


def parse_floor_channel(channel: str) -> int | None:
    prefix, _, raw_id = channel.partition(":")
    if prefix != "floor" or not raw_id.isdigit():
        return None
    return int(raw_id)


def can_subscribe(p: Principal, channel: str) -> bool:
    if channel == PATIO:
        return can_view_patio(p)
    floor_id = parse_floor_channel(channel)
    return floor_id is not None and can_view_floor(p, floor_id)


def location_channel(status: CarStatus | None, floor_id: int | None) -> str | None:
    if status == CarStatus.PATIO:
        return PATIO
    if status == CarStatus.ESTACIONADO and floor_id is not None:
        return floor_channel(floor_id)
    return None  # concluído (ou ainda não existia): não está em nenhum canal


@dataclass
class CarBroadcast:
    """Tudo o que o hub precisa para transmitir uma mudança de carro, já serializado."""

    car: dict[str, Any]
    task_type_id: int
    event_type: str
    status: CarStatus
    floor_id: int | None
    previous_status: CarStatus | None
    previous_floor_id: int | None


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    principal: Principal
    channels: set[str] = field(default_factory=set)

    def may_receive(self, channel: str, task_type_id: int | None = None) -> bool:
        if channel not in self.channels:
            return False
        if channel == PATIO:
            # Manobrista só recebe carros do pátio dos tipos sob sua responsabilidade.
            return task_type_id is not None and can_view_patio_car(self.principal, task_type_id)
        floor_id = parse_floor_channel(channel)
        return floor_id is not None and can_view_floor(self.principal, floor_id)


class Hub:
    def __init__(self) -> None:
        self.connections: set[Connection] = set()

    def add(self, connection: Connection) -> None:
        self.connections.add(connection)

    def remove(self, connection: Connection) -> None:
        self.connections.discard(connection)

    def subscribe(self, connection: Connection, channel: str) -> bool:
        if not can_subscribe(connection.principal, channel):
            return False
        connection.channels.add(channel)
        return True

    async def update_principal(self, principal: Principal) -> None:
        """Aplica mudança de papéis a conexões abertas e remove canais que deixaram de ser permitidos."""
        for connection in self.connections:
            if connection.principal.user_id == principal.user_id:
                connection.principal = principal
                connection.channels = {c for c in connection.channels if can_subscribe(principal, c)}

    async def _send(self, channel: str, message: dict[str, Any], task_type_id: int | None = None) -> None:
        for connection in list(self.connections):
            if not connection.may_receive(channel, task_type_id):
                continue
            try:
                await connection.websocket.send_json({**message, "channel": channel})
            except Exception:  # conexão caiu no meio do envio
                log.debug("Removing dead websocket connection", exc_info=True)
                self.remove(connection)

    async def publish_car(self, change: CarBroadcast) -> None:
        before = location_channel(change.previous_status, change.previous_floor_id)
        after = location_channel(change.status, change.floor_id)
        if before and before != after:
            await self._send(
                before,
                {"type": "car_removed", "event": change.event_type, "car_id": change.car["id"]},
                change.task_type_id,
            )
        if after:
            await self._send(
                after,
                {"type": "car_upserted", "event": change.event_type, "car": change.car},
                change.task_type_id,
            )

    async def publish_floor(self, floor_id: int, floor: dict[str, Any]) -> None:
        await self._send(floor_channel(floor_id), {"type": "floor_updated", "floor": floor})


hub = Hub()
