"""SmartCam SaaS backend integration tests (Phase 1)."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-guard-hub.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@smartcam.com"
ADMIN_PASSWORD = "SmartCam2026!"

TS = int(time.time())
USER_EMAIL = f"testuser+{TS}@smartcam.com"
USER_PASSWORD = "TestUser2026!"
USER2_EMAIL = f"testuser2+{TS}@smartcam.com"


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def user_token(s):
    r = s.post(f"{API}/auth/register", json={"email": USER_EMAIL, "name": "Test User", "password": USER_PASSWORD})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def user2_token():
    s2 = requests.Session()
    r = s2.post(f"{API}/auth/register", json={"email": USER2_EMAIL, "name": "Test User 2", "password": USER_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ============ HEALTH & PLANS ============
class TestHealth:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json() == {"status": "healthy"}

    def test_plans(self):
        r = requests.get(f"{API}/plans")
        assert r.status_code == 200
        plans = r.json()
        assert len(plans) == 3
        by_id = {p["id"]: p for p in plans}
        assert by_id["free"]["price_monthly"] == 0
        assert by_id["pro"]["price_monthly"] == 19
        assert by_id["enterprise"]["price_monthly"] == 49


# ============ AUTH ============
class TestAuth:
    def test_register_user(self, user_token):
        assert user_token and isinstance(user_token, str)

    def test_register_duplicate(self, s, user_token):
        r = s.post(f"{API}/auth/register", json={"email": USER_EMAIL, "name": "Dup", "password": USER_PASSWORD})
        assert r.status_code == 400
        assert "ya está registrado" in r.json()["detail"]

    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == USER_EMAIL
        assert "password_hash" not in data["user"]

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": "wrong"})
        assert r.status_code == 401
        assert r.json()["detail"] == "Credenciales inválidas"

    def test_me_with_bearer(self, user_token):
        r = requests.get(f"{API}/auth/me", headers=H(user_token))
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == USER_EMAIL
        assert "password_hash" not in d

    def test_me_without_auth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout(self, user_token):
        r = requests.post(f"{API}/auth/logout", headers=H(user_token))
        assert r.status_code == 200

    def test_admin_seed_role(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert d["role"] == "super_admin"
        assert d["subscription_plan"] == "enterprise"

    def test_google_session_invalid(self):
        r = requests.post(f"{API}/auth/google/session", json={"session_id": "fake-invalid-session-id"})
        assert r.status_code in (401, 502)


# ============ DEVICES ============
class TestDevices:
    def test_create_list_device(self, user_token):
        r = requests.post(f"{API}/devices", json={"name": "TEST_Rpi1", "location": "Sala"}, headers=H(user_token))
        assert r.status_code == 200
        d = r.json()
        assert d["pairing_token"]
        # Phase 2: token format XXXX-XXXX-XXXX (14 chars: 12 hex upper + 2 hyphens)
        assert len(d["pairing_token"]) == 14
        import re as _re
        assert _re.fullmatch(r"[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}", d["pairing_token"]), d["pairing_token"]
        assert d["is_paired"] is False
        device_id = d["id"]
        pytest.device_id = device_id
        pytest.pairing_token_initial = d["pairing_token"]

        r2 = requests.get(f"{API}/devices", headers=H(user_token))
        assert r2.status_code == 200
        ids = [x["id"] for x in r2.json()]
        assert device_id in ids

    def test_regenerate_token(self, user_token):
        r = requests.post(f"{API}/devices/{pytest.device_id}/regenerate-token", headers=H(user_token))
        assert r.status_code == 200
        d = r.json()
        assert d["pairing_token"] != pytest.pairing_token_initial
        assert d["is_paired"] is False

    def test_isolation_devices(self, user2_token):
        r = requests.get(f"{API}/devices", headers=H(user2_token))
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert pytest.device_id not in ids

    def test_delete_device_not_found(self, user2_token):
        r = requests.delete(f"{API}/devices/{pytest.device_id}", headers=H(user2_token))
        assert r.status_code == 404


# ============ CAMERAS ============
class TestCameras:
    def test_create_camera_invalid_device(self, user_token):
        r = requests.post(f"{API}/cameras", json={"name": "Cam1", "device_id": "nonexistent", "usb_index": 0}, headers=H(user_token))
        assert r.status_code == 404

    def test_create_camera(self, user_token):
        r = requests.post(f"{API}/cameras", json={"name": "TEST_Cam1", "device_id": pytest.device_id, "usb_index": 0}, headers=H(user_token))
        assert r.status_code == 200
        pytest.camera_id = r.json()["id"]

    def test_list_cameras(self, user_token):
        r = requests.get(f"{API}/cameras", headers=H(user_token))
        assert r.status_code == 200
        assert any(c["id"] == pytest.camera_id for c in r.json())

    def test_camera_isolation(self, user2_token):
        r = requests.get(f"{API}/cameras", headers=H(user2_token))
        assert r.status_code == 200
        assert all(c["id"] != pytest.camera_id for c in r.json())


# ============ EVENTS ============
class TestEvents:
    def test_list_events_empty(self, user_token):
        r = requests.get(f"{API}/events", headers=H(user_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_events_filters(self, user_token):
        r = requests.get(f"{API}/events?event_type=person", headers=H(user_token))
        assert r.status_code == 200
        r2 = requests.get(f"{API}/events?camera_id=abc", headers=H(user_token))
        assert r2.status_code == 200


# ============ DASHBOARD ============
class TestDashboard:
    def test_stats(self, user_token):
        r = requests.get(f"{API}/dashboard/stats", headers=H(user_token))
        assert r.status_code == 200
        d = r.json()
        for k in ["devices_count", "cameras_count", "events_24h", "suspicious_24h", "subscription_plan", "subscription_status"]:
            assert k in d
        assert d["devices_count"] >= 1
        assert d["cameras_count"] >= 1


# ============ ADMIN ============
class TestAdmin:
    def test_admin_stats_forbidden_for_user(self, user_token):
        r = requests.get(f"{API}/admin/stats", headers=H(user_token))
        assert r.status_code == 403

    def test_admin_stats(self, admin_token):
        r = requests.get(f"{API}/admin/stats", headers=H(admin_token))
        assert r.status_code == 200
        for k in ["total_users", "active_users", "total_devices", "total_cameras", "total_events", "paid_subscriptions"]:
            assert k in r.json()

    def test_admin_users(self, admin_token):
        r = requests.get(f"{API}/admin/users", headers=H(admin_token))
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == ADMIN_EMAIL for u in users)
        for u in users:
            assert "password_hash" not in u

    def test_admin_devices(self, admin_token):
        r = requests.get(f"{API}/admin/devices", headers=H(admin_token))
        assert r.status_code == 200

    def test_toggle_active(self, admin_token, user2_token):
        # Find user2 id
        users = requests.get(f"{API}/admin/users", headers=H(admin_token)).json()
        target = next(u for u in users if u["email"] == USER2_EMAIL)
        r = requests.patch(f"{API}/admin/users/{target['id']}/toggle-active", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        # re-enable
        r2 = requests.patch(f"{API}/admin/users/{target['id']}/toggle-active", headers=H(admin_token))
        assert r2.json()["is_active"] is True


# ============ BILLING ============
class TestBilling:
    def test_checkout_invalid_plan(self, user_token):
        r = requests.post(f"{API}/billing/checkout", json={"plan_id": "nonexistent", "origin_url": BASE_URL}, headers=H(user_token))
        assert r.status_code == 400

    def test_checkout_free_invalid(self, user_token):
        r = requests.post(f"{API}/billing/checkout", json={"plan_id": "free", "origin_url": BASE_URL}, headers=H(user_token))
        assert r.status_code == 400
        assert r.json()["detail"] == "Plan inválido"

    def test_checkout_pro(self, user_token):
        r = requests.post(f"{API}/billing/checkout", json={"plan_id": "pro", "origin_url": BASE_URL}, headers=H(user_token))
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d and "session_id" in d
        assert "stripe" in d["url"].lower()
        pytest.session_id = d["session_id"]

    def test_billing_status_owner(self, user_token):
        r = requests.get(f"{API}/billing/status/{pytest.session_id}", headers=H(user_token))
        assert r.status_code == 200
        assert "payment_status" in r.json()

    def test_billing_status_other_user_404(self, user2_token):
        r = requests.get(f"{API}/billing/status/{pytest.session_id}", headers=H(user2_token))
        assert r.status_code == 404


# ============ CLEANUP ============
class TestZCleanup:
    def test_delete_camera(self, user_token):
        r = requests.delete(f"{API}/cameras/{pytest.camera_id}", headers=H(user_token))
        assert r.status_code == 200

    def test_delete_device_cascades(self, user_token):
        r = requests.delete(f"{API}/devices/{pytest.device_id}", headers=H(user_token))
        assert r.status_code == 200
        # Confirm cameras removed
        r2 = requests.get(f"{API}/cameras", headers=H(user_token))
        assert all(c["device_id"] != pytest.device_id for c in r2.json())
