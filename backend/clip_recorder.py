"""Micro-video clip recorder.

Maintains a rolling buffer of recent JPEG frames per camera in memory, and on
event, captures pre-event + post-event frames and encodes them to a small MP4
file on disk. The resulting clip URL is patched back into the corresponding
event document in MongoDB.

Design constraints:
- Lightweight: no ffmpeg dependency. We use OpenCV's mp4v VideoWriter.
- Bounded memory: per-camera deque, capped by `PRE_SECONDS` of frames.
- Bounded disk: a startup cleanup task purges clips older than RETENTION_DAYS.

Defaults: 2s pre + 3s post = ~5s clip.
"""
from __future__ import annotations
import asyncio
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Tuple

logger = logging.getLogger("smartcam.clips")

# Tunables (can override via env)
PRE_SECONDS = float(os.environ.get("CLIP_PRE_SECONDS", "2.0"))
POST_SECONDS = float(os.environ.get("CLIP_POST_SECONDS", "3.0"))
RETENTION_DAYS = int(os.environ.get("CLIP_RETENTION_DAYS", "7"))
TARGET_FPS = int(os.environ.get("CLIP_FPS", "8"))
CLIPS_DIR = Path(os.environ.get("CLIPS_DIR", "/app/backend/clips"))
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# Per-camera rolling deque of (timestamp_seconds, jpeg_bytes)
_buffers: Dict[str, Deque[Tuple[float, bytes]]] = {}
# Cameras currently in mid-recording (avoid double-scheduling)
_recording: set = set()
# Cap each buffer to PRE_SECONDS at TARGET_FPS, but allow 50% headroom
_BUFFER_MAX_LEN = max(8, int(PRE_SECONDS * TARGET_FPS * 1.5))


def add_frame(camera_id: str, jpeg: bytes) -> None:
    """Push a JPEG frame into the camera's rolling buffer."""
    buf = _buffers.get(camera_id)
    if buf is None:
        buf = deque(maxlen=_BUFFER_MAX_LEN)
        _buffers[camera_id] = buf
    buf.append((time.time(), jpeg))


def _snapshot_pre_frames(camera_id: str) -> list[Tuple[float, bytes]]:
    """Return a snapshot copy of recent buffered frames for the camera."""
    buf = _buffers.get(camera_id)
    if not buf:
        return []
    cutoff = time.time() - PRE_SECONDS
    return [(ts, j) for (ts, j) in list(buf) if ts >= cutoff]


def _encode_clip_sync(frames: list[Tuple[float, bytes]], out_path: Path) -> bool:
    """Encode a list of (ts, jpeg) frames into an MP4. Returns True on success."""
    if not frames:
        return False
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        logger.error("opencv/numpy missing: %s", e)
        return False

    # Decode first frame to get dims
    first_arr = np.frombuffer(frames[0][1], dtype=np.uint8)
    first_img = cv2.imdecode(first_arr, cv2.IMREAD_COLOR)
    if first_img is None:
        return False
    h, w = first_img.shape[:2]

    tmp_path = out_path.with_suffix(".tmp.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(tmp_path), fourcc, TARGET_FPS, (w, h))
    if not writer.isOpened():
        logger.error("VideoWriter could not open %s", tmp_path)
        return False
    try:
        writer.write(first_img)
        for _ts, jpeg in frames[1:]:
            arr = np.frombuffer(jpeg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            if img.shape[:2] != (h, w):
                img = cv2.resize(img, (w, h))
            writer.write(img)
    finally:
        writer.release()

    if not tmp_path.exists() or tmp_path.stat().st_size < 1024:
        try: tmp_path.unlink(missing_ok=True)
        except Exception: pass
        return False
    tmp_path.replace(out_path)
    return True


async def _record_clip_task(event_id: str, camera_id: str) -> None:
    """Background task: gather pre+post frames, encode, patch event in DB."""
    if camera_id in _recording:
        logger.info("clip already recording for camera %s, skip event %s", camera_id, event_id)
        return
    _recording.add(camera_id)
    try:
        pre = _snapshot_pre_frames(camera_id)
        end_at = time.time() + POST_SECONDS
        # Collect post frames as they arrive
        last_seen_ts = pre[-1][0] if pre else 0.0
        while time.time() < end_at:
            await asyncio.sleep(0.15)
        # After post window, take everything we've buffered since the event
        buf = _buffers.get(camera_id) or deque()
        post = [(ts, j) for (ts, j) in list(buf) if ts > last_seen_ts]
        frames = pre + post
        if not frames:
            logger.warning("no frames for clip event=%s cam=%s", event_id, camera_id)
            return

        out_path = CLIPS_DIR / f"{event_id}.mp4"
        ok = await asyncio.get_event_loop().run_in_executor(
            None, _encode_clip_sync, frames, out_path
        )
        if not ok:
            logger.warning("encode failed for event=%s", event_id)
            return

        clip_url = f"/api/clips/{event_id}.mp4"
        # Patch event in Mongo
        try:
            from server import db
            await db.events.update_one(
                {"id": event_id},
                {"$set": {"clip_url": clip_url}},
            )
            logger.info("clip ready event=%s frames=%d size=%dB",
                        event_id, len(frames), out_path.stat().st_size)
        except Exception as e:  # pragma: no cover
            logger.error("could not patch event %s: %s", event_id, e)
    finally:
        _recording.discard(camera_id)


def schedule_clip(event_id: str, camera_id: str) -> None:
    """Fire-and-forget background recording task."""
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_record_clip_task(event_id, camera_id))
    except RuntimeError:
        # No running loop (shouldn't happen inside FastAPI handlers)
        logger.warning("no running loop; clip not scheduled for %s", event_id)


# ---------- Retention cleanup ----------
async def purge_old_clips_once() -> int:
    """Delete clips older than RETENTION_DAYS. Returns count removed."""
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed = 0
    if not CLIPS_DIR.exists():
        return 0
    for p in CLIPS_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except Exception:
            continue
    if removed:
        logger.info("purged %d old clips", removed)
    return removed


async def retention_loop() -> None:
    """Run cleanup once per hour."""
    while True:
        try:
            await purge_old_clips_once()
        except Exception as e:  # pragma: no cover
            logger.error("retention loop error: %s", e)
        await asyncio.sleep(3600)
