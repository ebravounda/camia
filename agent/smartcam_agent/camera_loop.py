"""USB camera scanning, thumbnail capture and motion detection."""
from __future__ import annotations

import base64
import glob
import os
import re
import sys
import threading
import time
from typing import List, Dict, Any, Optional

try:
    import cv2  # opencv-python or opencv-python-headless
except ImportError:  # noqa: F401
    cv2 = None  # type: ignore

from . import client


THUMB_INTERVAL_SEC = int(os.environ.get("SMARTCAM_THUMB_INTERVAL", "300"))  # 5 min
MOTION_CHECK_FPS = float(os.environ.get("SMARTCAM_MOTION_FPS", "4"))
MOTION_AREA_THRESHOLD = int(os.environ.get("SMARTCAM_MOTION_AREA", "1500"))  # pixels
MOTION_COOLDOWN_SEC = int(os.environ.get("SMARTCAM_MOTION_COOLDOWN", "30"))
THUMB_MAX_WIDTH = 480

# Camera capture defaults (override via env vars). MJPG @ 640x480 is a great
# default for Raspberry Pi 3B+: low CPU, compressed pixel format, plenty of fps.
CAM_WIDTH = int(os.environ.get("SMARTCAM_CAM_WIDTH", "640"))
CAM_HEIGHT = int(os.environ.get("SMARTCAM_CAM_HEIGHT", "480"))
CAM_FPS = int(os.environ.get("SMARTCAM_CAM_FPS", "15"))
CAM_FOURCC = os.environ.get("SMARTCAM_CAM_FOURCC", "MJPG")


# ---------------- USB camera scan ----------------
# V4L2 capability flag for video capture devices
_V4L2_CAP_VIDEO_CAPTURE = 0x00000001


def _is_capture_device(idx: int) -> bool:
    """Return True if /dev/video<idx> declares V4L2 video-capture capability."""
    path = f"/sys/class/video4linux/video{idx}/device_caps"
    try:
        with open(path) as f:
            caps = int(f.read().strip(), 16)
        return bool(caps & _V4L2_CAP_VIDEO_CAPTURE)
    except (OSError, ValueError):
        pass
    # Fallback to capabilities
    path = f"/sys/class/video4linux/video{idx}/capabilities"
    try:
        with open(path) as f:
            caps = int(f.read().strip(), 16)
        return bool(caps & _V4L2_CAP_VIDEO_CAPTURE)
    except (OSError, ValueError):
        return True  # if can't tell, don't filter out


def scan_usb_cameras() -> List[Dict[str, Any]]:
    """Return list of REAL capture cameras under /dev/video*.

    Filters out the Raspberry Pi's internal bcm2835 codec / ISP nodes and any
    nodes that don't declare V4L2 video-capture capability. Does NOT open the
    device via OpenCV (that's slow and noisy when probed against non-capture
    nodes). Resolution/format info will be filled by the per-camera worker.
    """
    nodes = sorted(glob.glob("/dev/video*"))
    cams: List[Dict[str, Any]] = []
    for node in nodes:
        m = re.match(r"/dev/video(\d+)$", node)
        if not m:
            continue
        idx = int(m.group(1))
        name = _v4l2_name(idx) or ""
        # Skip Pi's internal video nodes (codec, ISP, decoder)
        low = name.lower()
        if any(tag in low for tag in ("bcm2835", "rpi-", "isp", "codec", "decode")):
            continue
        # Skip non-capture devices (e.g. /dev/video1 metadata stream)
        if not _is_capture_device(idx):
            continue
        cams.append({"usb_index": idx, "name": name or f"video{idx}"})
    return cams


def _v4l2_name(idx: int) -> Optional[str]:
    path = f"/sys/class/video4linux/video{idx}/name"
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


# ---------------- Capture helpers ----------------
def _encode_thumbnail(frame) -> Optional[str]:
    """Resize and JPEG-encode a frame to base64."""
    if cv2 is None or frame is None:
        return None
    h, w = frame.shape[:2]
    if w > THUMB_MAX_WIDTH:
        scale = THUMB_MAX_WIDTH / float(w)
        frame = cv2.resize(frame, (THUMB_MAX_WIDTH, int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


# ---------------- Per-camera worker ----------------
def _worker(api_url: str, api_key: str, cam: Dict[str, Any], stop_event: threading.Event) -> None:
    """One thread per assigned camera. Runs motion detection + periodic thumbnails."""
    cam_id = cam["id"]
    usb_idx = int(cam.get("usb_index", 0))
    name = cam.get("name", f"cam{usb_idx}")
    print(f"[agent][cam:{name}] starting worker on /dev/video{usb_idx}")

    if cv2 is None:
        print(f"[agent][cam:{name}] OpenCV not installed; skipping")
        return

    cap = cv2.VideoCapture(usb_idx, cv2.CAP_V4L2)
    if not cap.isOpened():
        print(f"[agent][cam:{name}] cannot open /dev/video{usb_idx}", file=sys.stderr)
        return

    # Configure capture for low CPU usage (critical on Pi 3B+).
    # Order matters on some cameras: set FOURCC first, then resolution, then FPS.
    try:
        if len(CAM_FOURCC) == 4:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*CAM_FOURCC))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        cap.set(cv2.CAP_PROP_FPS, CAM_FPS)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or 0
        print(f"[agent][cam:{name}] capture configured: {actual_w}x{actual_h} @ {actual_fps:.0f}fps fourcc={CAM_FOURCC}")
    except Exception as e:
        print(f"[agent][cam:{name}] could not configure capture: {e}", file=sys.stderr)

    last_thumb_at = 0.0
    last_event_at = 0.0
    prev_gray = None
    period = 1.0 / max(0.5, MOTION_CHECK_FPS)

    try:
        while not stop_event.is_set():
            t0 = time.time()
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.5)
                continue

            # Motion detection (only if enabled on cam)
            if cam.get("enabled", True):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                if prev_gray is not None:
                    delta = cv2.absdiff(prev_gray, gray)
                    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    nonzero = int(cv2.countNonZero(thresh))
                    if nonzero > MOTION_AREA_THRESHOLD and (time.time() - last_event_at) > MOTION_COOLDOWN_SEC:
                        last_event_at = time.time()
                        thumb = _encode_thumbnail(frame)
                        severity = "high" if nonzero > MOTION_AREA_THRESHOLD * 4 else "medium" if nonzero > MOTION_AREA_THRESHOLD * 2 else "low"
                        try:
                            client.report_event(
                                api_url, api_key, cam_id,
                                event_type="motion",
                                severity=severity,
                                description=f"Movimiento detectado ({nonzero}px)",
                                thumbnail_b64=thumb,
                            )
                            print(f"[agent][cam:{name}] motion event reported ({nonzero}px, {severity})")
                        except Exception as e:
                            print(f"[agent][cam:{name}] failed to report event: {e}", file=sys.stderr)
                prev_gray = gray

            # Periodic thumbnail upload (panel preview)
            if (time.time() - last_thumb_at) >= THUMB_INTERVAL_SEC:
                last_thumb_at = time.time()
                thumb = _encode_thumbnail(frame)
                if thumb:
                    try:
                        client.upload_thumbnail(api_url, api_key, cam_id, thumb)
                    except Exception as e:
                        print(f"[agent][cam:{name}] thumb upload failed: {e}", file=sys.stderr)

            # frame pacing
            elapsed = time.time() - t0
            if elapsed < period:
                time.sleep(period - elapsed)
    finally:
        cap.release()
        print(f"[agent][cam:{name}] worker stopped")


# ---------------- Main camera loop ----------------
def run_camera_workers(api_url: str, api_key: str, stop_event: threading.Event) -> None:
    """Long-lived loop: fetch assigned cameras every minute and (re)spawn workers."""
    workers: Dict[str, threading.Thread] = {}
    while not stop_event.is_set():
        try:
            cams = client.get_assigned_cameras(api_url, api_key)
        except Exception as e:
            print(f"[agent][cams] failed to fetch assigned cameras: {e}", file=sys.stderr)
            stop_event.wait(30)
            continue

        # Start workers for new cams
        for c in cams:
            cid = c["id"]
            if not c.get("enabled", True):
                continue
            if cid not in workers or not workers[cid].is_alive():
                t = threading.Thread(target=_worker, args=(api_url, api_key, c, stop_event),
                                     name=f"cam-{cid[:8]}", daemon=True)
                workers[cid] = t
                t.start()

        # Note: stopping workers for removed cams requires per-worker stop events;
        # for simplicity here, removed cams keep running until process exit.

        stop_event.wait(60)
