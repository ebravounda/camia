"""Audio capture for SmartCam agent (Raspberry Pi).

Uses `arecord` (alsa-utils) as a subprocess to capture PCM s16le mono 16kHz
directly from the default ALSA input device. Auto-detects whether a mic is
available; if not, exits silently and audio is just disabled for that camera.

Bandwidth: 16000 samples/sec * 2 bytes = 32 KB/sec per camera — minimal.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, Any

from . import client


SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_BYTES = 2  # s16le
# Each chunk = 200ms = 3200 samples = 6400 bytes
CHUNK_SAMPLES = int(SAMPLE_RATE * 0.2)
CHUNK_BYTES = CHUNK_SAMPLES * SAMPLE_BYTES * CHANNELS

# Audio capture is opt-in via env (default ON if arecord found)
AUDIO_ENABLED = os.environ.get("SMARTCAM_AUDIO", "1") not in ("0", "false", "no")
AUDIO_DEVICE = os.environ.get("SMARTCAM_AUDIO_DEVICE", "default")


def has_audio_device() -> bool:
    """Quick probe: does this Pi have any ALSA capture device?"""
    if not shutil.which("arecord"):
        return False
    try:
        # `arecord -l` lists capture devices; exit code 0 + non-empty stdout
        out = subprocess.run(
            ["arecord", "-l"],
            capture_output=True, text=True, timeout=2,
        )
        return out.returncode == 0 and "card " in (out.stdout or "")
    except Exception:
        return False


def _spawn_arecord() -> subprocess.Popen:
    """Spawn arecord streaming raw PCM to stdout."""
    cmd = [
        "arecord",
        "-q",                       # quiet
        "-D", AUDIO_DEVICE,
        "-f", "S16_LE",
        "-c", str(CHANNELS),
        "-r", str(SAMPLE_RATE),
        "-t", "raw",
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)


def _audio_worker(api_url: str, api_key: str, cam: Dict[str, Any], stop_event: threading.Event) -> None:
    """One thread per camera that wants audio. Reads from arecord and uploads."""
    cam_id = cam["id"]
    name = cam.get("name", cam_id[:8])

    if not has_audio_device():
        print(f"[agent][audio:{name}] no ALSA capture device — skipping")
        return

    print(f"[agent][audio:{name}] starting (PCM s16le {SAMPLE_RATE}Hz mono)")
    backoff = 1
    while not stop_event.is_set():
        proc = None
        try:
            proc = _spawn_arecord()
            backoff = 1
            assert proc.stdout is not None
            while not stop_event.is_set():
                chunk = proc.stdout.read(CHUNK_BYTES)
                if not chunk:
                    print(f"[agent][audio:{name}] arecord EOF — restarting", file=sys.stderr)
                    break
                try:
                    client.upload_audio(api_url, api_key, cam_id, chunk)
                except Exception as e:
                    # Don't spam the log — only every ~10s
                    if int(time.time()) % 10 == 0:
                        print(f"[agent][audio:{name}] upload error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[agent][audio:{name}] worker error: {e}", file=sys.stderr)
        finally:
            if proc is not None:
                try: proc.terminate()
                except Exception: pass
                try: proc.wait(timeout=2)
                except Exception:
                    try: proc.kill()
                    except Exception: pass
        if stop_event.is_set():
            break
        # Backoff before retrying
        stop_event.wait(min(backoff, 30))
        backoff = min(backoff * 2, 30)


def run_audio_workers(api_url: str, api_key: str, stop_event: threading.Event) -> None:
    """Spawn one audio worker per assigned camera that has audio_enabled=True.

    Many setups have a single mic on the Pi; uploading the same audio for
    multiple cams isn't ideal but is acceptable for MVP — events on any cam
    will get the same audio track. Override with SMARTCAM_AUDIO=0 to disable.
    """
    if not AUDIO_ENABLED:
        print("[agent][audio] disabled via SMARTCAM_AUDIO=0")
        return
    if not has_audio_device():
        print("[agent][audio] no capture device on this Pi — audio off")
        return

    workers: Dict[str, threading.Thread] = {}
    while not stop_event.is_set():
        try:
            cams = client.get_assigned_cameras(api_url, api_key)
        except Exception:
            stop_event.wait(30)
            continue
        for c in cams:
            cid = c["id"]
            if not c.get("audio_enabled", True):
                continue
            if cid not in workers or not workers[cid].is_alive():
                t = threading.Thread(
                    target=_audio_worker, args=(api_url, api_key, c, stop_event),
                    name=f"aud-{cid[:8]}", daemon=True,
                )
                workers[cid] = t
                t.start()
        stop_event.wait(60)
