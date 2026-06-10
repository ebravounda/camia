"""Backend-side suspicious-behaviour detection.

For now: loud-audio events derived from PCM chunks received via /agent/audio.
The Pi agent already does object/motion/face detection locally; this module
focuses on signals only the backend can compute (audio RMS, cross-camera
patterns, etc.).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger("smartcam.suspicious")

# Tunables (override via env)
LOUD_RMS_THRESHOLD = float(os.environ.get("LOUD_RMS_THRESHOLD", "8000"))
LOUD_COOLDOWN_SEC = int(os.environ.get("LOUD_COOLDOWN_SEC", "30"))

# Per-camera last loud-event timestamp (cool-down)
_last_loud_at: dict[str, float] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_rms(pcm_s16le_bytes: bytes) -> float:
    """Compute RMS of a 16-bit signed little-endian PCM chunk. Returns 0–32767."""
    if not pcm_s16le_bytes:
        return 0.0
    try:
        import numpy as np
        samples = np.frombuffer(pcm_s16le_bytes, dtype=np.int16)
        if samples.size == 0:
            return 0.0
        x = samples.astype(np.float32)
        return float((x * x).mean() ** 0.5)
    except Exception:
        return 0.0


async def maybe_emit_loud_audio_event(
    db, camera_id: str, user_id: str, pcm_bytes: bytes,
) -> None:
    """If the chunk is loud and we're past cool-down, create a suspicious event.

    The micro-clip for this event is generated automatically because
    `clip_recorder.schedule_clip` reads from the same buffer that already has
    the audio we just received.
    """
    rms = compute_rms(pcm_bytes)
    if rms < LOUD_RMS_THRESHOLD:
        return
    now = time.time()
    if now - _last_loud_at.get(camera_id, 0.0) < LOUD_COOLDOWN_SEC:
        return
    _last_loud_at[camera_id] = now

    # Severity heuristic: louder = more severe
    severity = "high" if rms >= LOUD_RMS_THRESHOLD * 2 else "medium"

    # Lookup camera name for nicer event description (best-effort)
    cam_name = None
    try:
        cam = await db.cameras.find_one({"id": camera_id}, {"name": 1})
        cam_name = cam.get("name") if cam else None
    except Exception:
        pass

    from clip_recorder import schedule_clip
    from models import new_id

    event_id = new_id()
    doc = {
        "id": event_id,
        "user_id": user_id,
        "camera_id": camera_id,
        "camera_name": cam_name,
        "event_type": "loud_audio",
        "severity": severity,
        "description": f"Ruido fuerte detectado ({int(rms)} RMS)",
        "thumbnail_url": None,
        "clip_url": None,
        "clip_has_audio": True,  # by definition
        "metadata": {"rms": round(rms, 1), "threshold": LOUD_RMS_THRESHOLD},
        "created_at": _utcnow().isoformat(),
    }
    try:
        await db.events.insert_one(doc)
        await db.cameras.update_one(
            {"id": camera_id}, {"$set": {"last_event_at": doc["created_at"]}}
        )
        schedule_clip(event_id, camera_id)
        logger.info("loud_audio event camera=%s rms=%.0f sev=%s", camera_id, rms, severity)
    except Exception as e:  # pragma: no cover
        logger.error("failed to insert loud_audio event: %s", e)
