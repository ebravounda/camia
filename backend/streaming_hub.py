"""In-memory live frame hub: agent → backend → frontend.

Now supports both video and audio. The WebSocket protocol prefixes every
binary message with a 1-byte type marker:
    0x01  → JPEG video frame
    0x02  → PCM s16le mono audio chunk (16kHz)
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

VIDEO_MARKER = b"\x01"
AUDIO_MARKER = b"\x02"


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


async def _broadcast(camera_id: str, payload: bytes) -> None:
    subs = _subscribers.get(camera_id)
    if not subs:
        return
    dead = []
    for ws in list(subs):
        try:
            await ws.send_bytes(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        subs.discard(ws)


async def broadcast_frame(camera_id: str, jpeg: bytes) -> None:
    """Push JPEG bytes prefixed with VIDEO_MARKER to all subscribers."""
    await _broadcast(camera_id, VIDEO_MARKER + jpeg)


async def broadcast_audio(camera_id: str, pcm: bytes) -> None:
    """Push PCM bytes prefixed with AUDIO_MARKER to all subscribers."""
    await _broadcast(camera_id, AUDIO_MARKER + pcm)


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
