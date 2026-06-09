"""SmartCam SaaS Phase 2 — Raspberry Pi agent integration tests."""
import os
import re
import time
import io
import tarfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-guard-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TS = int(time.time())
USER_EMAIL = f"agentuser+{TS}@smartcam.com"
USER2_EMAIL = f"agentuser2+{TS}@smartcam.com"
PASSWORD = "TestUser2026!"


def H(token):
    return {"Authorization": f"Bearer {token}"}


def AG(api_key):
    return {"Authorization": f"Agent {api_key}"}


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{API}/auth/register", json={"email": USER_EMAIL, "name": "Agent U1", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def user2_token():
    r = requests.post(f"{API}/auth/register", json={"email": USER2_EMAIL, "name": "Agent U2", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def device_u1(user_token):
    r = requests.post(f"{API}/devices", json={"name": "TEST_PI_AGENT_1", "location": "Lab"}, headers=H(user_token))
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def device_u2(user2_token):
    r = requests.post(f"{API}/devices", json={"name": "TEST_PI_AGENT_2", "location": "Other"}, headers=H(user2_token))
    assert r.status_code == 200, r.text
    return r.json()


# =================== Token format ===================
class TestPairingTokenFormat:
    def test_token_format_create(self, device_u1):
        tok = device_u1["pairing_token"]
        assert len(tok) == 14
        assert re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", tok), tok

    def test_token_format_regenerate(self, user_token, device_u1):
        r = requests.post(f"{API}/devices/{device_u1['id']}/regenerate-token", headers=H(user_token))
        assert r.status_code == 200
        d = r.json()
        assert re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", d["pairing_token"])
        assert d["pairing_token"] != device_u1["pairing_token"]
        assert d["is_paired"] is False
        assert d.get("agent_api_key") in (None, "")
        # Persist new token back into the shared device dict
        device_u1["pairing_token"] = d["pairing_token"]


# =================== Pairing ===================
class TestPair:
    def test_pair_invalid_token(self):
        r = requests.post(f"{API}/agent/pair", json={"token": "ZZZZ-ZZZZ-ZZZZ", "hostname": "x"})
        assert r.status_code == 404
        assert "inv" in r.json()["detail"].lower() or "no encontrado" in r.json()["detail"].lower()

    def test_pair_missing_token(self):
        r = requests.post(f"{API}/agent/pair", json={"token": "", "hostname": "x"})
        assert r.status_code in (400, 422)

    def test_pair_success(self, device_u1):
        payload = {
            "token": device_u1["pairing_token"],
            "hostname": "pi-test-host",
            "agent_version": "0.2.0",
            "ip_address": "192.168.1.55",
        }
        r = requests.post(f"{API}/agent/pair", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["device_id"] == device_u1["id"]
        assert d["api_key"].startswith("sca_")
        assert d["api_url"].endswith("/api")
        assert d["user_id"]
        assert d["name"] == "TEST_PI_AGENT_1"
        device_u1["api_key"] = d["api_key"]

    def test_pair_token_reusable_until_regenerate(self, device_u1):
        """Pairing again with same token (since not regenerated) should still work (idempotent re-pair)."""
        r = requests.post(f"{API}/agent/pair", json={"token": device_u1["pairing_token"], "hostname": "pi2"})
        assert r.status_code == 200
        # New api_key issued; update fixture
        device_u1["api_key"] = r.json()["api_key"]

    def test_device_marked_paired(self, user_token, device_u1):
        r = requests.get(f"{API}/devices", headers=H(user_token))
        assert r.status_code == 200
        dev = next(x for x in r.json() if x["id"] == device_u1["id"])
        assert dev["is_paired"] is True
        assert dev["status"] == "online"
        assert dev.get("hostname") == "pi2"
        assert dev.get("agent_version") == "0.2.0" or dev.get("agent_version") is not None


# =================== Heartbeat ===================
class TestHeartbeat:
    def test_heartbeat_no_auth(self):
        r = requests.post(f"{API}/agent/heartbeat", json={})
        assert r.status_code == 401

    def test_heartbeat_bad_auth(self):
        r = requests.post(f"{API}/agent/heartbeat", json={}, headers=AG("sca_invalid_xxx"))
        assert r.status_code == 401
        assert "inv" in r.json()["detail"].lower() or "vac" in r.json()["detail"].lower()

    def test_heartbeat_success(self, user_token, device_u1):
        api_key = device_u1["api_key"]
        body = {"cpu_temp": 47.3, "cpu_usage": 12.5, "ip_address": "10.0.0.42", "agent_version": "0.2.0"}
        r = requests.post(f"{API}/agent/heartbeat", json=body, headers=AG(api_key))
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True

        # Verify owner sees updated fields
        r2 = requests.get(f"{API}/devices", headers=H(user_token))
        dev = next(x for x in r2.json() if x["id"] == device_u1["id"])
        assert dev["cpu_temp"] == 47.3
        assert dev["cpu_usage"] == 12.5
        assert dev["ip_address"] == "10.0.0.42"
        assert dev["agent_version"] == "0.2.0"
        assert dev["status"] == "online"


# =================== Detected cameras ===================
class TestDetectedCameras:
    def test_report_detected_cameras(self, device_u1, user_token):
        body = {"cameras": [
            {"usb_index": 0, "name": "USB Cam A", "width": 1280, "height": 720},
            {"usb_index": 2, "name": "USB Cam B", "width": 640, "height": 480},
        ]}
        r = requests.post(f"{API}/agent/detected-cameras", json=body, headers=AG(device_u1["api_key"]))
        assert r.status_code == 200
        assert r.json()["received"] == 2


# =================== Agent fetch cameras ===================
class TestAgentCameras:
    def test_agent_cameras_empty(self, device_u1):
        r = requests.get(f"{API}/agent/cameras", headers=AG(device_u1["api_key"]))
        assert r.status_code == 200
        assert "cameras" in r.json()

    def test_agent_cameras_bad_auth(self):
        r = requests.get(f"{API}/agent/cameras", headers=AG("sca_bad"))
        assert r.status_code == 401

    def test_create_camera_and_agent_sees_it(self, user_token, device_u1):
        r = requests.post(f"{API}/cameras",
                          json={"name": "TEST_AGENT_CAM", "device_id": device_u1["id"], "usb_index": 0},
                          headers=H(user_token))
        assert r.status_code == 200
        cam = r.json()
        device_u1["camera_id"] = cam["id"]

        r2 = requests.get(f"{API}/agent/cameras", headers=AG(device_u1["api_key"]))
        assert r2.status_code == 200
        cams = r2.json()["cameras"]
        assert any(c["id"] == cam["id"] for c in cams)
        # last_thumbnail must be projected out
        for c in cams:
            assert "last_thumbnail" not in c


# =================== Thumbnail upload ===================
DUMMY_JPEG_B64 = (
    # base64 of a minimal byte string; doesn't need to be real JPEG
    "/9j/4AAQSkZJRgABAQAAAQABAAD//gA7Q1JFQVRPUjogZ2QtanBlZyB2MS4wICh1c2luZyBJSkcgSlBFRyB2NjIpLCBxdWFsaXR5ID0gOTAK"
)


class TestThumbnail:
    def test_thumbnail_success(self, device_u1):
        r = requests.post(f"{API}/agent/thumbnail",
                          json={"camera_id": device_u1["camera_id"], "thumbnail_b64": DUMMY_JPEG_B64},
                          headers=AG(device_u1["api_key"]))
        assert r.status_code == 200, r.text

    def test_thumbnail_too_big(self, device_u1):
        big = "A" * 260_000
        r = requests.post(f"{API}/agent/thumbnail",
                          json={"camera_id": device_u1["camera_id"], "thumbnail_b64": big},
                          headers=AG(device_u1["api_key"]))
        assert r.status_code == 413

    def test_thumbnail_wrong_device(self, device_u2, device_u1):
        # device_u2 has no api_key yet — pair first
        r0 = requests.post(f"{API}/agent/pair", json={"token": device_u2["pairing_token"], "hostname": "pi-u2"})
        assert r0.status_code == 200
        device_u2["api_key"] = r0.json()["api_key"]

        # u2 agent tries to upload thumbnail to u1's camera → 404
        r = requests.post(f"{API}/agent/thumbnail",
                          json={"camera_id": device_u1["camera_id"], "thumbnail_b64": DUMMY_JPEG_B64},
                          headers=AG(device_u2["api_key"]))
        assert r.status_code == 404
        assert "no asignada" in r.json()["detail"].lower() or "cámara" in r.json()["detail"].lower()

    def test_thumbnail_visible_in_cameras_list(self, user_token, device_u1):
        r = requests.get(f"{API}/cameras", headers=H(user_token))
        cam = next(c for c in r.json() if c["id"] == device_u1["camera_id"])
        assert cam.get("last_thumbnail") == DUMMY_JPEG_B64
        assert cam["status"] == "live"


# =================== Event reporting ===================
class TestEvents:
    def test_event_success(self, user_token, device_u1):
        body = {
            "camera_id": device_u1["camera_id"],
            "event_type": "motion",
            "severity": "medium",
            "description": "Movimiento detectado test",
            "thumbnail_b64": DUMMY_JPEG_B64,
        }
        r = requests.post(f"{API}/agent/event", json=body, headers=AG(device_u1["api_key"]))
        assert r.status_code == 200, r.text
        ev = r.json()
        assert ev["event_type"] == "motion"
        assert ev["severity"] == "medium"
        assert ev["camera_id"] == device_u1["camera_id"]
        assert ev["thumbnail_url"].startswith("data:image/jpeg;base64,")

        # Owner can list it
        r2 = requests.get(f"{API}/events", headers=H(user_token))
        assert r2.status_code == 200
        events = r2.json()
        assert any(e["id"] == ev["id"] for e in events)

    def test_event_isolation_cross_user(self, device_u1, device_u2, user2_token):
        # u2 agent tries to report event on u1's camera → 404
        body = {"camera_id": device_u1["camera_id"], "event_type": "motion", "severity": "low"}
        r = requests.post(f"{API}/agent/event", json=body, headers=AG(device_u2["api_key"]))
        assert r.status_code == 404

        # And u2 user should not see u1's events
        r2 = requests.get(f"{API}/events", headers=H(user2_token))
        u1_cam = device_u1["camera_id"]
        assert all(e["camera_id"] != u1_cam for e in r2.json())


# =================== Agent download ===================
class TestAgentDownload:
    def test_download_no_auth(self):
        r = requests.get(f"{API}/agent/download")
        assert r.status_code == 401

    def test_download_success(self, user_token):
        r = requests.get(f"{API}/agent/download", headers=H(user_token))
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("application/gzip")
        # Verify tar.gz contents
        buf = io.BytesIO(r.content)
        with tarfile.open(fileobj=buf, mode="r:gz") as tf:
            names = tf.getnames()
        assert any(n.endswith("smartcam-agent/install.sh") for n in names), names[:10]
        assert any(n.endswith("smartcam-agent/smartcam_agent/agent.py") for n in names), names[:10]
        assert any(n.endswith("smartcam-agent/smartcam_agent/client.py") for n in names)
        assert any(n.endswith("smartcam-agent/smartcam_agent/heartbeat.py") for n in names)
        assert any(n.endswith("smartcam-agent/smartcam_agent/camera_loop.py") for n in names)


# =================== Cleanup ===================
class TestZCleanup:
    def test_cleanup(self, user_token, user2_token, device_u1, device_u2):
        requests.delete(f"{API}/cameras/{device_u1['camera_id']}", headers=H(user_token))
        requests.delete(f"{API}/devices/{device_u1['id']}", headers=H(user_token))
        requests.delete(f"{API}/devices/{device_u2['id']}", headers=H(user2_token))
