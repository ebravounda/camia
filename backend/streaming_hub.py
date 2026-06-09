"""In-memory live frame hub: agent → backend → frontend MJPEG stream.

We deliberately keep the latest frame per camera ONLY in memory (no DB writes
per frame). A single uvicorn process handles all subscribers.
"""
from __future__ import annotations
import time
from typing import Dict, Tuple

# camera_id -> (timestamp, jpeg_bytes)
LIVE_FRAMES: Dict[str, Tuple[float, bytes]] = {}

# Discard frames older than this when serving to subscribers
MAX_FRAME_AGE_SEC = 5.0


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
