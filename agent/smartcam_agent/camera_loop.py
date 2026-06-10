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
MOTION_CHECK_FPS = float(os.environ.get("SMARTCAM_MOTION_FPS", "3"))
MOTION_AREA_THRESHOLD = int(os.environ.get("SMARTCAM_MOTION_AREA", "1500"))  # pixels
MOTION_COOLDOWN_SEC = int(os.environ.get("SMARTCAM_MOTION_COOLDOWN", "30"))
THUMB_MAX_WIDTH = 480

# Backend AI analysis (YOLO on server)
AI_ENABLED = os.environ.get("SMARTCAM_AI", "1") not in ("0", "false", "no")
AI_INTERVAL = float(os.environ.get("SMARTCAM_AI_INTERVAL", "2.5"))  # seconds between analyses
AI_JPEG_QUALITY = int(os.environ.get("SMARTCAM_AI_QUALITY", "70"))
AI_MAX_WIDTH = int(os.environ.get("SMARTCAM_AI_MAX_WIDTH", "480"))

# Live streaming defaults. STREAM_MAX_WIDTH=0 means use the camera's full
# capture resolution (recommended now that HD/FHD is selectable per-camera).
STREAM_FPS = float(os.environ.get("SMARTCAM_STREAM_FPS", "20"))
STREAM_MAX_WIDTH = int(os.environ.get("SMARTCAM_STREAM_MAX_WIDTH", "0"))
STREAM_JPEG_QUALITY = int(os.environ.get("SMARTCAM_STREAM_QUALITY", "85"))
STREAM_ENABLED = os.environ.get("SMARTCAM_STREAM", "1") not in ("0", "false", "no")
HUD_ENABLED = os.environ.get("SMARTCAM_HUD", "1") not in ("0", "false", "no")

# Suspicious behaviour rules
NIGHT_HOUR_START = int(os.environ.get("SMARTCAM_NIGHT_START", "22"))  # 22:00
NIGHT_HOUR_END = int(os.environ.get("SMARTCAM_NIGHT_END", "6"))      # 06:00
SUSPICIOUS_COOLDOWN_SEC = int(os.environ.get("SMARTCAM_SUSP_COOLDOWN", "120"))

# Resolution presets (overridden per-camera from backend config)
RESOLUTION_PRESETS = {
    "SD":  (640, 480),
    "HD":  (1280, 720),
    "FHD": (1920, 1080),
}

# Camera capture defaults (override via env vars). MJPG is mandatory for HD/FHD
# on Pi 3B+ to avoid the bandwidth wall of raw YUYV.
CAM_FPS = int(os.environ.get("SMARTCAM_CAM_FPS", "20"))
CAM_FOURCC = os.environ.get("SMARTCAM_CAM_FOURCC", "MJPG")
# Default resolution fallback when backend doesn't specify
DEFAULT_RESOLUTION = os.environ.get("SMARTCAM_DEFAULT_RES", "HD")


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


def _encode_stream_jpeg(frame) -> Optional[bytes]:
    """Resize (if STREAM_MAX_WIDTH>0) and JPEG-encode a frame as raw bytes for live streaming."""
    if cv2 is None or frame is None:
        return None
    if STREAM_MAX_WIDTH > 0:
        h, w = frame.shape[:2]
        if w > STREAM_MAX_WIDTH:
            scale = STREAM_MAX_WIDTH / float(w)
            frame = cv2.resize(frame, (STREAM_MAX_WIDTH, int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY])
    if not ok:
        return None
    return buf.tobytes()


def _encode_ai_jpeg(frame) -> Optional[bytes]:
    if cv2 is None or frame is None:
        return None
    h, w = frame.shape[:2]
    if w > AI_MAX_WIDTH:
        scale = AI_MAX_WIDTH / float(w)
        frame = cv2.resize(frame, (AI_MAX_WIDTH, int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), AI_JPEG_QUALITY])
    if not ok:
        return None
    return buf.tobytes()


# Color per class for boxes (BGR)
_AI_COLORS = {
    "person": (0, 255, 0), "car": (255, 100, 0), "motorcycle": (255, 100, 100),
    "truck": (255, 50, 50), "bus": (255, 50, 0), "bicycle": (200, 200, 0),
    "dog": (0, 200, 255), "cat": (180, 0, 255), "bird": (255, 200, 100),
}


def _draw_ai_detections(frame, detections, scale_x=1.0, scale_y=1.0) -> None:
    """Draw labeled boxes for backend YOLO detections."""
    for d in detections:
        label = d.get("label", "?")
        color = _AI_COLORS.get(label, (0, 220, 220))
        x = int(d["x"] * scale_x)
        y = int(d["y"] * scale_y)
        w = int(d["w"] * scale_x)
        h = int(d["h"] * scale_y)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        text = f"{d.get('label_es', label).upper()} {int(d.get('confidence', 0) * 100)}%"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x, y - th - 8), (x + tw + 8, y), color, -1)
        cv2.putText(frame, text, (x + 4, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


# ---------------- Face detection (Haar cascade, fast on Pi 3B+) ----------------
FACE_DETECT_INTERVAL = float(os.environ.get("SMARTCAM_FACE_INTERVAL", "0.5"))  # seconds between detections
FACE_SAVE_COOLDOWN = int(os.environ.get("SMARTCAM_FACE_COOLDOWN", "60"))  # seconds between face events per cam
FACE_ENABLED = os.environ.get("SMARTCAM_FACE", "1") not in ("0", "false", "no")
FACE_MIN_SIZE = int(os.environ.get("SMARTCAM_FACE_MIN_SIZE", "40"))

_face_cascade = None


def _get_face_cascade():
    """Load Haar cascade from any of the common paths on Pi/Debian/Ubuntu."""
    global _face_cascade
    if cv2 is None:
        return None
    if _face_cascade is not None:
        return _face_cascade if _face_cascade is not False else None

    candidates = []
    # 1) pip wheel install (opencv-python / opencv-contrib-python)
    try:
        if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            candidates.append(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except Exception:
        pass
    # 2) Debian / Raspberry Pi OS apt package paths
    candidates.extend([
        "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml",
        "/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
    ])
    # 3) Last-resort glob (limited depth)
    try:
        import glob as _glob
        for p in _glob.glob("/usr/share/*/haarcascades/haarcascade_frontalface_default.xml"):
            candidates.append(p)
    except Exception:
        pass

    for path in candidates:
        try:
            cascade = cv2.CascadeClassifier(path)
            if not cascade.empty():
                print(f"[agent] face cascade loaded from {path}")
                _face_cascade = cascade
                return _face_cascade
        except Exception:
            continue
    print("[agent] WARN: face cascade not found — face detection disabled", file=sys.stderr)
    _face_cascade = False
    return None


def _detect_faces(frame) -> list:
    """Return list of (x, y, w, h) face rectangles."""
    cascade = _get_face_cascade()
    if cascade is None:
        return []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.2, minNeighbors=5,
        minSize=(FACE_MIN_SIZE, FACE_MIN_SIZE),
    )
    return [tuple(int(v) for v in f) for f in faces]


def _draw_faces(frame, faces) -> None:
    """Draw yellow bounding boxes on detected faces (in place)."""
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
        label = "CARA"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x, y - th - 6), (x + tw + 6, y), (0, 255, 255), -1)
        cv2.putText(frame, label, (x + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def _draw_motion_boxes(frame, rects) -> None:
    """Draw cyan boxes around moving objects (in place)."""
    for (x, y, w, h) in rects:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 200, 0), 1)


def _draw_hud(frame, cam_name: str, faces, motion_rects, recent_event: bool,
              suspicious: bool, is_night: bool) -> None:
    """Overlay a 'security camera' style HUD on the frame."""
    h, w = frame.shape[:2]

    # Status pill (top-left)
    if suspicious:
        status = "SOSPECHOSO"
        color = (0, 0, 255)  # red BGR
    elif motion_rects:
        status = "MOVIMIENTO"
        color = (0, 165, 255)  # orange
    elif faces:
        status = "ROSTRO DETECTADO"
        color = (0, 255, 255)  # yellow
    else:
        status = "VIGILANDO"
        color = (0, 255, 0)  # green

    # Top bar background
    cv2.rectangle(frame, (0, 0), (w, 32), (0, 0, 0), -1)

    # Pulse dot + status
    cv2.circle(frame, (16, 16), 5, color, -1)
    cv2.putText(frame, status, (30, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    # Detection counters (center top)
    info = f"Caras: {len(faces)}  Mov: {len(motion_rects)}"
    cv2.putText(frame, info, (w // 2 - 70, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)

    # Timestamp (top-right)
    ts = time.strftime("%H:%M:%S")
    cv2.putText(frame, ts, (w - 80, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)

    # Bottom bar
    cv2.rectangle(frame, (0, h - 24), (w, h), (0, 0, 0), -1)
    cv2.putText(frame, f"SmartCam | {cam_name}", (10, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (180, 180, 180), 1, cv2.LINE_AA)
    if is_night:
        cv2.putText(frame, "NOCHE", (w - 60, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (255, 180, 0), 1, cv2.LINE_AA)


def _is_night() -> bool:
    h = time.localtime().tm_hour
    if NIGHT_HOUR_START <= NIGHT_HOUR_END:
        return NIGHT_HOUR_START <= h < NIGHT_HOUR_END
    return h >= NIGHT_HOUR_START or h < NIGHT_HOUR_END  # wraps midnight


def _crop_face(frame, face_rect, pad: int = 25):
    x, y, w, h = face_rect
    h_f, w_f = frame.shape[:2]
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(w_f, x + w + pad)
    y1 = min(h_f, y + h + pad)
    return frame[y0:y1, x0:x1]


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

    # Try to open /dev/videoN with retries (device may be transiently busy).
    cap = None
    for attempt in range(1, 6):
        cap = cv2.VideoCapture(usb_idx, cv2.CAP_V4L2)
        if cap.isOpened():
            break
        try:
            cap.release()
        except Exception:
            pass
        cap = None
        print(f"[agent][cam:{name}] /dev/video{usb_idx} busy, retry {attempt}/5 in 3s", file=sys.stderr)
        if stop_event.wait(3):
            return
    if cap is None or not cap.isOpened():
        print(f"[agent][cam:{name}] cannot open /dev/video{usb_idx} after retries", file=sys.stderr)
        return

    # Configure capture for low CPU usage (critical on Pi 3B+).
    # Order matters on some cameras: set FOURCC first, then resolution, then FPS.
    # Resolution comes from per-camera config: SD/HD/FHD.
    cam_res = (cam.get("resolution") or DEFAULT_RESOLUTION).upper()
    cap_w, cap_h = RESOLUTION_PRESETS.get(cam_res, RESOLUTION_PRESETS["HD"])
    try:
        if len(CAM_FOURCC) == 4:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*CAM_FOURCC))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, cap_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cap_h)
        cap.set(cv2.CAP_PROP_FPS, CAM_FPS)
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or 0
        print(f"[agent][cam:{name}] capture {cam_res} ({cap_w}x{cap_h}) → actual {actual_w}x{actual_h} @ {actual_fps:.0f}fps fourcc={CAM_FOURCC}")
    except Exception as e:
        print(f"[agent][cam:{name}] could not configure capture: {e}", file=sys.stderr)

    last_thumb_at = 0.0
    last_event_at = 0.0
    last_stream_at = 0.0
    last_motion_at = 0.0
    last_face_detect_at = 0.0
    last_face_saved_at = 0.0
    last_suspicious_at = 0.0
    last_ai_at = 0.0
    last_ai_detections = []
    last_ai_frame_size = None
    # AI runs in a background thread; these are shared state
    _ai_state = {"detections": [], "frame_size": None}
    _ai_inflight = [False]  # list-as-cell so closure can mutate
    last_faces = []
    last_motion_rects = []
    stream_interval = 1.0 / max(1.0, STREAM_FPS)
    motion_interval = 1.0 / max(0.5, MOTION_CHECK_FPS)
    prev_gray = None
    # Loop tick = a bit faster than the highest consumer (stream)
    loop_period = max(0.02, stream_interval * 0.75)

    try:
        while not stop_event.is_set():
            t0 = time.time()
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.5)
                continue

            # Motion detection (rate-limited, decoupled from stream)
            if cam.get("enabled", True) and (time.time() - last_motion_at) >= motion_interval:
                last_motion_at = time.time()
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                if prev_gray is not None:
                    delta = cv2.absdiff(prev_gray, gray)
                    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    nonzero = int(cv2.countNonZero(thresh))

                    # Extract motion contours for HUD overlay
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    motion_rects = []
                    for c in contours:
                        if cv2.contourArea(c) > 500:
                            motion_rects.append(cv2.boundingRect(c))
                    last_motion_rects = motion_rects

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
                else:
                    last_motion_rects = []
                prev_gray = gray
            else:
                last_motion_rects = []  # noqa: F841 - used later in stream overlay

            # Periodic thumbnail upload (panel preview)
            if (time.time() - last_thumb_at) >= THUMB_INTERVAL_SEC:
                last_thumb_at = time.time()
                thumb = _encode_thumbnail(frame)
                if thumb:
                    try:
                        client.upload_thumbnail(api_url, api_key, cam_id, thumb)
                    except Exception as e:
                        print(f"[agent][cam:{name}] thumb upload failed: {e}", file=sys.stderr)

            # Live stream upload (high-rate, raw JPEG, no DB writes)
            if STREAM_ENABLED and (time.time() - last_stream_at) >= stream_interval:
                last_stream_at = time.time()

                # Face detection (slower rate to save CPU)
                if FACE_ENABLED and (time.time() - last_face_detect_at) >= FACE_DETECT_INTERVAL:
                    last_face_detect_at = time.time()
                    try:
                        last_faces = _detect_faces(frame)
                    except Exception as e:
                        if int(time.time()) % 30 == 0:
                            print(f"[agent][cam:{name}] face detect error: {e}", file=sys.stderr)
                        last_faces = []

                    # Save first face as an event (rate-limited)
                    if last_faces and (time.time() - last_face_saved_at) >= FACE_SAVE_COOLDOWN:
                        last_face_saved_at = time.time()
                        try:
                            face_crop = _crop_face(frame, last_faces[0])
                            face_b64 = _encode_thumbnail(face_crop)
                            if face_b64:
                                client.report_event(
                                    api_url, api_key, cam_id,
                                    event_type="unknown_face",
                                    severity="medium",
                                    description=f"{len(last_faces)} cara{'s' if len(last_faces) > 1 else ''} detectada{'s' if len(last_faces) > 1 else ''}",
                                    thumbnail_b64=face_b64,
                                )
                                print(f"[agent][cam:{name}] face event saved ({len(last_faces)} face(s))")
                        except Exception as e:
                            print(f"[agent][cam:{name}] face event error: {e}", file=sys.stderr)

                # SUSPICIOUS detection: night + (face OR significant motion)
                night = _is_night()
                suspicious_now = night and (last_faces or len(last_motion_rects) >= 2)
                if suspicious_now and (time.time() - last_suspicious_at) > SUSPICIOUS_COOLDOWN_SEC:
                    last_suspicious_at = time.time()
                    try:
                        thumb_b64 = _encode_thumbnail(frame)
                        desc = "Actividad nocturna: " + (
                            "rostro + movimiento" if last_faces and last_motion_rects
                            else ("rostro detectado" if last_faces else "movimiento intenso")
                        )
                        client.report_event(
                            api_url, api_key, cam_id,
                            event_type="suspicious",
                            severity="high",
                            description=desc,
                            thumbnail_b64=thumb_b64,
                        )
                        print(f"[agent][cam:{name}] SUSPICIOUS event saved: {desc}")
                    except Exception as e:
                        print(f"[agent][cam:{name}] suspicious event error: {e}", file=sys.stderr)

                # Backend AI analysis (YOLO on server) - throttled, NON-BLOCKING
                # Runs in a background daemon thread so the stream loop never
                # waits on the HTTP request (this was the main source of stutter
                # every AI_INTERVAL seconds on the previous version).
                if AI_ENABLED and (time.time() - last_ai_at) >= AI_INTERVAL and not _ai_inflight[0]:
                    last_ai_at = time.time()
                    ai_jpeg = _encode_ai_jpeg(frame)
                    if ai_jpeg:
                        h_orig, w_orig = frame.shape[:2]
                        scale = AI_MAX_WIDTH / float(w_orig) if w_orig > AI_MAX_WIDTH else 1.0
                        ai_frame_size_local = (int(w_orig * scale), int(h_orig * scale))

                        def _ai_worker(jpeg_payload: bytes, frame_size_xy):
                            try:
                                dets = client.analyze_frame(api_url, api_key, cam_id, jpeg_payload)
                                _ai_state["detections"] = dets
                                _ai_state["frame_size"] = frame_size_xy
                                if dets:
                                    labels = ", ".join(sorted({d.get("label_es", d["label"]) for d in dets}))
                                    print(f"[agent][cam:{name}] AI detected: {labels}")
                            except Exception as e:
                                if int(time.time()) % 30 == 0:
                                    print(f"[agent][cam:{name}] AI analyze error: {e}", file=sys.stderr)
                            finally:
                                _ai_inflight[0] = False

                        _ai_inflight[0] = True
                        threading.Thread(
                            target=_ai_worker,
                            args=(ai_jpeg, ai_frame_size_local),
                            name=f"ai-{cam_id[:8]}",
                            daemon=True,
                        ).start()

                last_ai_detections = _ai_state["detections"]
                last_ai_frame_size = _ai_state["frame_size"]

                # Build the display frame with overlays
                display_frame = frame
                if HUD_ENABLED or last_faces or last_motion_rects or last_ai_detections:
                    display_frame = frame.copy()
                    if last_motion_rects:
                        _draw_motion_boxes(display_frame, last_motion_rects)
                    # Draw AI detections (scale boxes from AI frame back to current frame)
                    if last_ai_detections and last_ai_frame_size:
                        h_cur, w_cur = display_frame.shape[:2]
                        sx = w_cur / float(last_ai_frame_size[0]) if last_ai_frame_size[0] else 1.0
                        sy = h_cur / float(last_ai_frame_size[1]) if last_ai_frame_size[1] else 1.0
                        _draw_ai_detections(display_frame, last_ai_detections, sx, sy)
                    if last_faces:
                        _draw_faces(display_frame, last_faces)
                    if HUD_ENABLED:
                        recent = (time.time() - last_event_at) < 5
                        susp_active = (time.time() - last_suspicious_at) < 5
                        _draw_hud(display_frame, name, last_faces, last_motion_rects, recent, susp_active, night)

                jpeg = _encode_stream_jpeg(display_frame)
                if jpeg:
                    try:
                        client.upload_live_frame(api_url, api_key, cam_id, jpeg)
                    except Exception as e:
                        if int(time.time()) % 30 == 0:
                            print(f"[agent][cam:{name}] stream upload error: {e}", file=sys.stderr)

            # frame pacing
            elapsed = time.time() - t0
            if elapsed < loop_period:
                time.sleep(loop_period - elapsed)
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
