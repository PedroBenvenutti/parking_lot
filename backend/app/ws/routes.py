from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.db import SessionLocal
from app.services.auth import user_id_from_token
from app.services.errors import Unauthorized
from app.services.permissions import Principal, load_principal
from app.ws.hub import Connection, hub

router = APIRouter()

# Código de fechamento próprio (faixa 4000-4999 é livre para aplicações).
CLOSE_UNAUTHORIZED = 4401


def _principal_from_token(token: str) -> Principal:
    user_id = user_id_from_token(token)
    with SessionLocal() as db:
        return load_principal(db, user_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    """Protocolo:
    cliente -> {"action": "subscribe" | "unsubscribe", "channel": "patio" | "floor:<id>"}
    servidor -> {"type": "subscribed" | "unsubscribed" | "error"
                 | "car_upserted" | "car_removed" | "floor_updated", ...}
    """
    try:
        principal = await run_in_threadpool(_principal_from_token, token)
    except Unauthorized:
        await websocket.accept()
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return

    await websocket.accept()
    connection = Connection(websocket=websocket, principal=principal)
    hub.add(connection)
    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action") if isinstance(message, dict) else None
            channel = str(message.get("channel", "")) if isinstance(message, dict) else ""
            if action == "subscribe":
                if hub.subscribe(connection, channel):
                    await websocket.send_json({"type": "subscribed", "channel": channel})
                else:
                    await websocket.send_json(
                        {"type": "error", "channel": channel, "message": "Sem permissão para este canal"}
                    )
            elif action == "unsubscribe":
                connection.channels.discard(channel)
                await websocket.send_json({"type": "unsubscribed", "channel": channel})
            else:
                await websocket.send_json({"type": "error", "message": "Ação desconhecida"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(connection)
