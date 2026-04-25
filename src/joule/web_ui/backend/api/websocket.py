"""WebSocket router for real-time run updates.

Clients connect to ``/ws`` and can subscribe to individual run IDs to
receive progress events.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages WebSocket connections and per-run subscriptions."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.run_subscribers: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected  (%d total)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Clean up subscriptions
        for run_id in list(self.run_subscribers):
            subs = self.run_subscribers[run_id]
            if websocket in subs:
                subs.remove(websocket)
            if not subs:
                del self.run_subscribers[run_id]
        logger.info("WebSocket disconnected (%d total)", len(self.active_connections))

    async def send_personal(self, message: dict[str, Any], websocket: WebSocket) -> None:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for conn in self.active_connections:
            try:
                await conn.send_text(json.dumps(message))
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)

    async def send_run_update(self, run_id: str, data: dict[str, Any]) -> None:
        subs = self.run_subscribers.get(run_id, [])
        dead: list[WebSocket] = []
        msg = json.dumps({"type": "run_update", "run_id": run_id, "data": data})
        for conn in subs:
            try:
                await conn.send_text(msg)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect(d)

    def subscribe(self, run_id: str, websocket: WebSocket) -> None:
        self.run_subscribers.setdefault(run_id, []).append(websocket)

    def unsubscribe(self, run_id: str, websocket: WebSocket) -> None:
        subs = self.run_subscribers.get(run_id, [])
        if websocket in subs:
            subs.remove(websocket)
        if not subs and run_id in self.run_subscribers:
            del self.run_subscribers[run_id]


# Singleton
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal({"type": "error", "error": "invalid JSON"}, websocket)
                continue

            msg_type = message.get("type")

            if msg_type == "subscribe_run":
                run_id = message.get("run_id")
                if run_id:
                    manager.subscribe(run_id, websocket)
                    await manager.send_personal({"type": "subscription_confirmed", "run_id": run_id}, websocket)

            elif msg_type == "unsubscribe_run":
                run_id = message.get("run_id")
                if run_id:
                    manager.unsubscribe(run_id, websocket)
                    await manager.send_personal({"type": "unsubscription_confirmed", "run_id": run_id}, websocket)

            elif msg_type == "ping":
                await manager.send_personal({"type": "pong", "timestamp": message.get("timestamp")}, websocket)

            else:
                await manager.send_personal({"type": "echo", "original": message}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        manager.disconnect(websocket)
