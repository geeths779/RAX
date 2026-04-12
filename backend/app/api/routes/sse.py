"""SSE endpoint for real-time pipeline status broadcasting.

Replaces the previous WebSocket approach with Server-Sent Events:
 - Unidirectional (server → client) — perfect for pipeline status
 - Built-in browser reconnection via EventSource
 - Works over standard HTTP (no upgrade required)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pub/Sub Broadcaster ──────────────────────────────────────────────────────

class SSEBroadcaster:
    """Manages per-job subscriber queues for SSE event fan-out."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = set()
        self._subscribers[job_id].add(queue)
        logger.info("SSE subscribed: job_id=%s (total=%d)", job_id, len(self._subscribers[job_id]))
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        if job_id in self._subscribers:
            self._subscribers[job_id].discard(queue)
            if not self._subscribers[job_id]:
                del self._subscribers[job_id]
        logger.info("SSE unsubscribed: job_id=%s", job_id)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Push event to every subscriber listening on *job_id*."""
        for q in list(self._subscribers.get(job_id, [])):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # drop if subscriber is too slow


# Global singleton
broadcaster = SSEBroadcaster()


# ── Callback factory (used by resumes.py pipeline runner) ─────────────────────

def make_sse_callback(job_id: str):
    """Create a StatusCallback for the PipelineOrchestrator.

    Returns an async function matching:
        async callback(resume_id: str, stage: str, status: str) -> None
    """

    async def _callback(resume_id: str, stage: str, status: str) -> None:
        await broadcaster.publish(job_id, {
            "resume_id": resume_id,
            "stage": stage,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return _callback


# ── Token validation ──────────────────────────────────────────────────────────

def _validate_token(token: str | None) -> bool:
    settings = get_settings()
    if settings.ENVIRONMENT == "development" and not token:
        return True
    if not token:
        return False
    try:
        jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return True
    except JWTError:
        return False


# ── SSE endpoint ──────────────────────────────────────────────────────────────

@router.get("/pipeline/{job_id}/events")
async def pipeline_events(
    request: Request,
    job_id: str,
    token: str | None = Query(default=None),
):
    """SSE stream for real-time pipeline stage updates for a given job."""
    if not _validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid token")

    queue = broadcaster.subscribe(job_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment prevents proxy/browser timeout
                    yield ": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx/reverse-proxy buffering
        },
    )
