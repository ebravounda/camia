"""In-memory live frame hub: agent → backend → frontend.

Supports two delivery modes:
- HTTP MJPEG (fallback): polls LIVE_FRAMES dict.
- WebSocket: subscribers receive frames the instant they arrive (lowest latency).
"""
from __future__ import annotations
import asyncio
import time
from typing import Dict, Set, Tuple
from fastapi import WebSocket

LIVE_FRAMES: Dict[str, Tuple[float, bytes]] = {}
MAX_FRAME_AGE_SEC = 5.0

# camera_id -> set of subscriber WebSockets
_subscribers: Dict[str, Set[WebSocket]] = {}


def add_subscriber(camera_id: str, ws: WebSocket) -> None:
    _subscribers.setdefault(camera_id, set()).add(ws)


def remove_subscriber(camera_id: str, ws: WebSocket) -> None:
    s = _subscribers.get(camera_id)
    if s:
        s.discard(ws)
        if not s:
            _subscribers.pop(camera_id, None)


def subscriber_count(camera_id: str) -> int:
    return len(_subscribers.get(camera_id, ()))


async def broadcast_frame(camera_id: str, jpeg: bytes) -> None:
    """Push JPEG bytes to every subscribed WebSocket for this camera."""
    subs = _subscribers.get(camera_id)
    if not subs:
        return
    dead = []
    for ws in list(subs):
        try:
            await ws.send_bytes(jpeg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        subs.discard(ws)


def set_frame(camera_id: str, jpeg: bytes) -> None:
    LIVE_FRAMES[camera_id] = (time.time(), jpeg)


def get_frame(camera_id: str):
    entry = LIVE_FRAMES.get(camera_id)
    if not entry:
        return None
    ts, jpeg = entry
    if time.time() - ts > MAX_FRAME_AGE_SEC:
        return None
    return entry
