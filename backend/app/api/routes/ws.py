"""WebSocket endpoint for real-time pipeline status broadcasting."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections grouped by job_id."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if job_id not in self._connections:
            self._connections[job_id] = set()
        self._connections[job_id].add(websocket)
        logger.info("WS connected: job_id=%s (total=%d)", job_id, len(self._connections[job_id]))

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        if job_id in self._connections:
            self._connections[job_id].discard(websocket)
            if not self._connections[job_id]:
                del self._connections[job_id]
        logger.info("WS disconnected: job_id=%s", job_id)

    async def broadcast(self, job_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connections listening for a given job_id."""
        if job_id not in self._connections:
            return
        dead: list[WebSocket] = []
        # Iterate over a snapshot to avoid RuntimeError if set changes mid-iteration
        for ws in list(self._connections.get(job_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[job_id].discard(ws)


# Global singleton shared across the application
manager = ConnectionManager()


def make_ws_callback(ws_manager: ConnectionManager, job_id: str):
    """Create a StatusCallback function for the PipelineOrchestrator.

    Returns an async function matching:
        async callback(resume_id: str, stage: str, status: str) -> None
    """

    async def _callback(resume_id: str, stage: str, status: str) -> None:
        await ws_manager.broadcast(job_id, {
            "resume_id": resume_id,
            "stage": stage,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return _callback


def _validate_ws_token(token: str | None) -> bool:
    """Validate a JWT token from WebSocket query param. Returns True if valid."""
    settings = get_settings()
    # In development, allow unauthenticated WS connections
    if settings.ENVIRONMENT == "development" and not token:
        return True
    if not token:
        return False
    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return True
    except JWTError:
        return False


@router.websocket("/ws/pipeline/{job_id}")
async def pipeline_ws(
    websocket: WebSocket,
    job_id: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for receiving real-time pipeline stage updates."""
    if not _validate_ws_token(token):
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(job_id, websocket)
    try:
        # Keep connection alive — client sends ping/pong or we just wait
        while True:
            # Wait for any incoming message (client can send pings)
            data = await websocket.receive_text()
            # Echo back for heartbeat
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
    except Exception:
        manager.disconnect(job_id, websocket)
