"""Micro-video clip recorder with audio support.

Maintains per-camera rolling buffers of JPEG frames + PCM audio chunks.
On event, encodes a small MP4 (H.264 + AAC) using PyAV (ffmpeg bindings).

- Video: H.264 / yuv420p / TARGET_FPS, original capture resolution preserved
- Audio: AAC LC / 16 kHz / mono — sourced from the Pi mic if available
- 5s clip = 2s pre + 3s post
- 7-day retention loop purges old files
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

# Tunables (override via env)
PRE_SECONDS = float(os.environ.get("CLIP_PRE_SECONDS", "2.0"))
POST_SECONDS = float(os.environ.get("CLIP_POST_SECONDS", "3.0"))
RETENTION_DAYS = int(os.environ.get("CLIP_RETENTION_DAYS", "7"))
TARGET_FPS = int(os.environ.get("CLIP_FPS", "10"))
AUDIO_SAMPLE_RATE = int(os.environ.get("AUDIO_SAMPLE_RATE", "16000"))  # 16 kHz mono PCM s16le
CLIPS_DIR = Path(os.environ.get("CLIPS_DIR", "/app/backend/clips"))
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# Per-camera rolling buffers
_video_buf: Dict[str, Deque[Tuple[float, bytes]]] = {}
_audio_buf: Dict[str, Deque[Tuple[float, bytes]]] = {}  # (ts, pcm_s16le_mono)
_recording: set = set()

# Cap by time, with 50% headroom
_VBUF_MAX = max(16, int(PRE_SECONDS * TARGET_FPS * 1.5))
# Each audio chunk is ~200ms (3200 samples). Pre = 2s → 10 chunks. Headroom x1.5
_ABUF_MAX = max(16, int(PRE_SECONDS * 5 * 1.5))


def add_frame(camera_id: str, jpeg: bytes) -> None:
    buf = _video_buf.get(camera_id)
    if buf is None:
        buf = deque(maxlen=_VBUF_MAX)
        _video_buf[camera_id] = buf
    buf.append((time.time(), jpeg))


def add_audio(camera_id: str, pcm_s16le_mono: bytes) -> None:
    buf = _audio_buf.get(camera_id)
    if buf is None:
        buf = deque(maxlen=_ABUF_MAX)
        _audio_buf[camera_id] = buf
    buf.append((time.time(), pcm_s16le_mono))


def _snapshot(buf: Dict[str, Deque[Tuple[float, bytes]]], camera_id: str) -> list[Tuple[float, bytes]]:
    b = buf.get(camera_id)
    if not b:
        return []
    cutoff = time.time() - PRE_SECONDS
    return [(ts, j) for (ts, j) in list(b) if ts >= cutoff]


def _encode_clip_sync(
    video_frames: list[Tuple[float, bytes]],
    audio_chunks: list[Tuple[float, bytes]],
    out_path: Path,
) -> bool:
    """Encode JPEG frames + PCM audio chunks into a single MP4 (H.264 + AAC)."""
    if not video_frames:
        return False
    try:
        import av  # PyAV
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        logger.error("missing libs (av/cv2/np): %s", e)
        return False

    # Probe first frame for dimensions
    first_arr = np.frombuffer(video_frames[0][1], dtype=np.uint8)
    first_img = cv2.imdecode(first_arr, cv2.IMREAD_COLOR)
    if first_img is None:
        return False
    h, w = first_img.shape[:2]
    # H.264 needs even dimensions
    if w % 2: w -= 1
    if h % 2: h -= 1

    tmp_path = out_path.with_suffix(".tmp.mp4")
    container = av.open(str(tmp_path), mode="w", format="mp4",
                         options={"movflags": "+faststart"})  # mobile-friendly
    try:
        # Video stream
        vstream = container.add_stream("libx264", rate=TARGET_FPS)
        vstream.width = w
        vstream.height = h
        vstream.pix_fmt = "yuv420p"
        vstream.options = {"preset": "veryfast", "tune": "zerolatency", "crf": "23"}

        # Audio stream (only if we have chunks)
        astream = None
        if audio_chunks:
            astream = container.add_stream("aac", rate=AUDIO_SAMPLE_RATE)
            astream.layout = "mono"
            astream.bit_rate = 64_000  # 64 kbps mono

        # Video: assign sequential pts based on TARGET_FPS
        for i, (_ts, jpg) in enumerate(video_frames):
            arr = np.frombuffer(jpg, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            if img.shape[0] != h or img.shape[1] != w:
                img = cv2.resize(img, (w, h))
            # BGR -> RGB
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            vframe = av.VideoFrame.from_ndarray(img_rgb, format="rgb24")
            vframe.pts = i
            for packet in vstream.encode(vframe):
                container.mux(packet)
        # Flush video
        for packet in vstream.encode(None):
            container.mux(packet)

        # Audio: concatenate PCM bytes, split into AudioFrames of 1024 samples
        if astream is not None and audio_chunks:
            import numpy as _np
            pcm = b"".join(c for (_t, c) in audio_chunks)
            samples = _np.frombuffer(pcm, dtype=_np.int16)
            if samples.size:
                FRAME_SAMPLES = 1024
                # PyAV s16 mono expects shape (1, N)
                a_pts = 0
                total = samples.size
                idx = 0
                while idx < total:
                    chunk = samples[idx: idx + FRAME_SAMPLES]
                    idx += FRAME_SAMPLES
                    if chunk.size == 0:
                        break
                    aframe = av.AudioFrame.from_ndarray(
                        chunk.reshape(1, -1), format="s16", layout="mono"
                    )
                    aframe.rate = AUDIO_SAMPLE_RATE
                    aframe.pts = a_pts
                    a_pts += chunk.size
                    for packet in astream.encode(aframe):
                        container.mux(packet)
                # Flush audio
                for packet in astream.encode(None):
                    container.mux(packet)
    except Exception as e:
        logger.exception("PyAV encode failed: %s", e)
        try: tmp_path.unlink(missing_ok=True)
        except Exception: pass
        return False
    finally:
        try: container.close()
        except Exception: pass

    if not tmp_path.exists() or tmp_path.stat().st_size < 1024:
        try: tmp_path.unlink(missing_ok=True)
        except Exception: pass
        return False
    tmp_path.replace(out_path)
    return True


async def _record_clip_task(event_id: str, camera_id: str) -> None:
    if camera_id in _recording:
        logger.info("clip already recording for cam=%s skip event=%s", camera_id, event_id)
        return
    _recording.add(camera_id)
    try:
        v_pre = _snapshot(_video_buf, camera_id)
        a_pre = _snapshot(_audio_buf, camera_id)
        marker = time.time()
        await asyncio.sleep(POST_SECONDS)

        # Post-event: take everything after marker
        v_buf = _video_buf.get(camera_id) or deque()
        v_post = [(ts, j) for (ts, j) in list(v_buf) if ts > marker]
        a_buf = _audio_buf.get(camera_id) or deque()
        a_post = [(ts, j) for (ts, j) in list(a_buf) if ts > marker]
        v_frames = v_pre + v_post
        a_chunks = a_pre + a_post

        if not v_frames:
            logger.warning("no video frames for event=%s cam=%s", event_id, camera_id)
            return

        out_path = CLIPS_DIR / f"{event_id}.mp4"
        ok = await asyncio.get_event_loop().run_in_executor(
            None, _encode_clip_sync, v_frames, a_chunks, out_path
        )
        if not ok:
            logger.warning("encode failed event=%s", event_id)
            return

        clip_url = f"/api/clips/{event_id}.mp4"
        has_audio = bool(a_chunks)
        try:
            from server import db
            await db.events.update_one(
                {"id": event_id},
                {"$set": {"clip_url": clip_url, "clip_has_audio": has_audio}},
            )
            logger.info(
                "clip ready event=%s v=%d a=%d size=%dB audio=%s",
                event_id, len(v_frames), len(a_chunks), out_path.stat().st_size, has_audio,
            )
        except Exception as e:  # pragma: no cover
            logger.error("patch event %s failed: %s", event_id, e)
    finally:
        _recording.discard(camera_id)


def schedule_clip(event_id: str, camera_id: str) -> None:
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_record_clip_task(event_id, camera_id))
    except RuntimeError:
        logger.warning("no running loop; clip not scheduled %s", event_id)


# ---------- Retention cleanup ----------
async def purge_old_clips_once() -> int:
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
    while True:
        try:
            await purge_old_clips_once()
        except Exception as e:  # pragma: no cover
            logger.error("retention loop error: %s", e)
        await asyncio.sleep(3600)
