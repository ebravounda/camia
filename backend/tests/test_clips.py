"""Phase 3 tests: micro-clip recording + retention + StaticFiles mount.

Covers:
- POST /api/agent/frame pushes frames into the clip rolling buffer.
- After POST /api/agent/event, schedule_clip is triggered; ~3.5s later the
  event document should have a clip_url and GET /api/clips/{id}.mp4 returns
  a real MP4 with status 200 and content-type video/mp4.
- Static serving: existing clips in /app/backend/clips are reachable.
"""
import os
import io
import time
import base64
import struct
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@smartcam.com"
ADMIN_PASSWORD = "SmartCam2026!"


def _make_jpeg(w=64, h=48, color=(0, 128, 0)) -> bytes:
    """Build a tiny solid-color JPEG using PIL (pillow is in backend deps)."""
    from PIL import Image
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def paired(admin_token):
    """Create a device, pair it, attach a camera. Returns dict with ids/keys."""
    h = {"Authorization": f"Bearer {admin_token}"}
    # Create device
    r = requests.post(f"{API}/devices", json={"name": "TEST_CLIP_PI", "location": "lab"}, headers=h)
    assert r.status_code == 200, r.text
    dev = r.json()
    # Pair
    r2 = requests.post(f"{API}/agent/pair", json={"token": dev["pairing_token"], "hostname": "clip-test"})
    assert r2.status_code == 200, r2.text
    pair = r2.json()
    # Create camera
    r3 = requests.post(f"{API}/cameras",
                       json={"name": "TEST_CLIP_CAM", "device_id": dev["id"], "usb_index": 0},
                       headers=h)
    assert r3.status_code == 200, r3.text
    cam = r3.json()
    yield {"device_id": dev["id"], "api_key": pair["api_key"], "camera_id": cam["id"], "admin_h": h}
    # Cleanup
    requests.delete(f"{API}/cameras/{cam['id']}", headers=h)
    requests.delete(f"{API}/devices/{dev['id']}", headers=h)


class TestClipsStatic:
    def test_static_mount_serves_existing_clip(self):
        """At least one real MP4 exists; serve it via /api/clips/<file>."""
        clips_dir = "/app/backend/clips"
        files = [f for f in os.listdir(clips_dir) if f.endswith(".mp4")]
        if not files:
            pytest.skip("no clips on disk")
        r = requests.get(f"{API}/clips/{files[0]}")
        assert r.status_code == 200
        assert r.headers.get("content-type") == "video/mp4"
        assert len(r.content) > 1024  # non-empty

    def test_unknown_clip_returns_404(self):
        r = requests.get(f"{API}/clips/does-not-exist.mp4")
        assert r.status_code == 404


class TestClipPipeline:
    def test_frame_upload_then_event_then_clip(self, paired):
        agent_h = {"Authorization": f"Agent {paired['api_key']}",
                   "X-Camera-Id": paired["camera_id"],
                   "Content-Type": "image/jpeg"}
        jpeg = _make_jpeg()
        # Push ~25 frames over ~2.5s to populate pre-event buffer
        for _ in range(25):
            r = requests.post(f"{API}/agent/frame", data=jpeg, headers=agent_h)
            assert r.status_code == 200, r.text
            time.sleep(0.1)

        # Emit event
        ev_h = {"Authorization": f"Agent {paired['api_key']}"}
        r = requests.post(
            f"{API}/agent/event",
            json={"camera_id": paired["camera_id"], "event_type": "person",
                  "severity": "medium", "description": "TEST_CLIP_EVENT"},
            headers=ev_h,
        )
        assert r.status_code == 200, r.text
        event_id = r.json()["id"]

        # Keep streaming frames during POST window so encoder gets >0 post frames
        for _ in range(35):  # ~3.5s of post frames
            requests.post(f"{API}/agent/frame", data=jpeg, headers=agent_h)
            time.sleep(0.1)

        # Wait extra for encode to land on disk + DB patch
        deadline = time.time() + 8
        clip_url = None
        while time.time() < deadline:
            r2 = requests.get(f"{API}/events", headers=paired["admin_h"], params={"limit": 50})
            assert r2.status_code == 200
            found = next((e for e in r2.json() if e["id"] == event_id), None)
            if found and found.get("clip_url"):
                clip_url = found["clip_url"]
                break
            time.sleep(0.5)

        assert clip_url, f"clip_url never set for event {event_id}"
        assert clip_url == f"/api/clips/{event_id}.mp4"

        # Verify the MP4 is served
        r3 = requests.get(f"{BASE_URL}{clip_url}")
        assert r3.status_code == 200
        assert r3.headers.get("content-type") == "video/mp4"
        assert len(r3.content) > 1024
        # Basic MP4 magic check: bytes 4..8 == 'ftyp'
        assert r3.content[4:8] == b"ftyp", "Not a valid MP4 (missing ftyp box)"
