"""App routes: devices, cameras, events, super admin."""
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from models import (
    Device, DeviceCreate, Camera, CameraCreate, Event, Plan,
    UserPublic, utcnow, new_id,
)
from auth import get_current_user, require_super_admin
from streaming_hub import get_frame, LIVE_FRAMES


router = APIRouter(tags=["app"])


# ===== PLANS (public) =====
PLANS = [
    Plan(
        id="free",
        name="Free",
        price_monthly=0.0,
        features=[
            "1 Raspberry Pi",
            "1 cámara USB",
            "Detección de movimiento básica",
            "Almacenamiento 24h",
            "Alertas por email",
        ],
        max_cameras=1,
        max_devices=1,
        storage_days=1,
    ),
    Plan(
        id="pro",
        name="Pro",
        price_monthly=19.0,
        features=[
            "1 Raspberry Pi",
            "Hasta 4 cámaras USB",
            "IA YOLOv8 + reconocimiento facial",
            "Almacenamiento 7 días en Google Drive",
            "Alertas WhatsApp ilimitadas",
            "Timeline de eventos con miniaturas",
        ],
        max_cameras=4,
        max_devices=1,
        storage_days=7,
    ),
    Plan(
        id="enterprise",
        name="Enterprise",
        price_monthly=49.0,
        features=[
            "Múltiples Raspberry Pi",
            "Cámaras ilimitadas",
            "Detección de comportamientos sospechosos",
            "Almacenamiento 30 días",
            "Múltiples destinatarios WhatsApp",
            "Soporte prioritario 24/7",
            "Panel multi-sucursal",
        ],
        max_cameras=999,
        max_devices=999,
        storage_days=30,
    ),
]


@router.get("/plans", response_model=List[Plan])
async def list_plans():
    return PLANS


def get_plan_by_id(plan_id: str) -> Optional[Plan]:
    for p in PLANS:
        if p.id == plan_id:
            return p
    return None


# ===== DEVICES (Raspberry Pi) =====
@router.get("/devices", response_model=List[Device])
async def list_devices(user: dict = Depends(get_current_user)):
    from server import db
    docs = await db.devices.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return docs


def _gen_pairing_token() -> str:
    """Generate a XXXX-XXXX-XXXX pairing token (12 hex chars + 2 hyphens)."""
    raw = secrets.token_hex(6).upper()  # 12 hex chars guaranteed
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


@router.post("/devices", response_model=Device)
async def create_device(payload: DeviceCreate, user: dict = Depends(get_current_user)):
    from server import db
    token = _gen_pairing_token()
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "name": payload.name,
        "location": payload.location,
        "pairing_token": token,
        "agent_api_key": None,
        "agent_version": None,
        "hostname": None,
        "is_paired": False,
        "status": "offline",
        "last_seen": None,
        "cpu_temp": None,
        "cpu_usage": None,
        "ip_address": None,
        "created_at": utcnow().isoformat(),
    }
    await db.devices.insert_one(doc)
    return doc


@router.delete("/devices/{device_id}")
async def delete_device(device_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.devices.delete_one({"id": device_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    await db.cameras.delete_many({"device_id": device_id, "user_id": user["id"]})
    return {"message": "Dispositivo eliminado"}


@router.post("/devices/{device_id}/regenerate-token", response_model=Device)
async def regenerate_pairing_token(device_id: str, user: dict = Depends(get_current_user)):
    from server import db
    new_token = _gen_pairing_token()
    result = await db.devices.find_one_and_update(
        {"id": device_id, "user_id": user["id"]},
        {"$set": {
            "pairing_token": new_token,
            "is_paired": False,
            "agent_api_key": None,
            "status": "offline",
        }},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    return result


# ===== CAMERAS =====
@router.get("/cameras", response_model=List[Camera])
async def list_cameras(user: dict = Depends(get_current_user)):
    from server import db
    docs = await db.cameras.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return docs


@router.post("/cameras", response_model=Camera)
async def create_camera(payload: CameraCreate, user: dict = Depends(get_current_user)):
    from server import db
    device = await db.devices.find_one({"id": payload.device_id, "user_id": user["id"]})
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "device_id": payload.device_id,
        "name": payload.name,
        "usb_index": payload.usb_index,
        "enabled": payload.enabled,
        "status": "offline",
        "last_event_at": None,
        "detection_zones": [],
        "created_at": utcnow().isoformat(),
    }
    await db.cameras.insert_one(doc)
    return doc


@router.delete("/cameras/{camera_id}")
async def delete_camera(camera_id: str, user: dict = Depends(get_current_user)):
    from server import db
    result = await db.cameras.delete_one({"id": camera_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return {"message": "Cámara eliminada"}


# ===== LIVE STREAMING (MJPEG over HTTP) =====
@router.get("/cameras/{camera_id}/snapshot.jpg")
async def camera_snapshot(camera_id: str, user: dict = Depends(get_current_user)):
    """Returns the latest JPEG frame for a camera (poll-based clients)."""
    from server import db
    cam = await db.cameras.find_one({"id": camera_id, "user_id": user["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    entry = get_frame(camera_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Sin frame disponible")
    _, jpeg = entry
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
    )


@router.get("/cameras/{camera_id}/stream.mjpg")
async def camera_stream_mjpeg(camera_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Multipart MJPEG stream — browser displays it natively as a video."""
    from server import db
    cam = await db.cameras.find_one({"id": camera_id, "user_id": user["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    boundary = "smartcamframe"

    async def generator():
        last_ts = 0.0
        try:
            # Initial bytes so browser knows this is an MJPEG stream
            while True:
                if await request.is_disconnected():
                    return
                entry = get_frame(camera_id)
                if entry:
                    ts, jpeg = entry
                    if ts != last_ts:
                        last_ts = ts
                        header = (
                            f"--{boundary}\r\n"
                            f"Content-Type: image/jpeg\r\n"
                            f"Content-Length: {len(jpeg)}\r\n\r\n"
                        ).encode()
                        yield header + jpeg + b"\r\n"
                await asyncio.sleep(0.05)  # poll 20Hz, actually limited by agent push rate
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        generator(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-store, must-revalidate", "Pragma": "no-cache"},
    )


# ===== EVENTS =====
@router.get("/events", response_model=List[Event])
async def list_events(
    user: dict = Depends(get_current_user),
    limit: int = Query(50, le=200),
    event_type: Optional[str] = None,
    camera_id: Optional[str] = None,
):
    from server import db
    query: dict = {"user_id": user["id"]}
    if event_type:
        query["event_type"] = event_type
    if camera_id:
        query["camera_id"] = camera_id
    docs = await db.events.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


# ===== DASHBOARD STATS =====
@router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    from server import db
    devices_count = await db.devices.count_documents({"user_id": user["id"]})
    cameras_count = await db.cameras.count_documents({"user_id": user["id"]})
    online_cameras = await db.cameras.count_documents({"user_id": user["id"]}, )  # placeholder
    # Events in last 24h
    cutoff = (utcnow() - timedelta(hours=24)).isoformat()
    events_24h = await db.events.count_documents({"user_id": user["id"], "created_at": {"$gte": cutoff}})
    suspicious_24h = await db.events.count_documents({
        "user_id": user["id"],
        "event_type": "suspicious",
        "created_at": {"$gte": cutoff},
    })
    return {
        "devices_count": devices_count,
        "cameras_count": cameras_count,
        "online_cameras": online_cameras,
        "events_24h": events_24h,
        "suspicious_24h": suspicious_24h,
        "subscription_plan": user.get("subscription_plan", "free"),
        "subscription_status": user.get("subscription_status", "inactive"),
    }


# ===== SUPER ADMIN =====
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/stats")
async def admin_stats(_admin: dict = Depends(require_super_admin)):
    from server import db
    return {
        "total_users": await db.users.count_documents({}),
        "active_users": await db.users.count_documents({"is_active": True}),
        "total_devices": await db.devices.count_documents({}),
        "total_cameras": await db.cameras.count_documents({}),
        "total_events": await db.events.count_documents({}),
        "paid_subscriptions": await db.users.count_documents({"subscription_status": "active", "subscription_plan": {"$ne": "free"}}),
    }


@admin_router.get("/users", response_model=List[UserPublic])
async def admin_list_users(_admin: dict = Depends(require_super_admin)):
    from server import db
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    return docs


@admin_router.patch("/users/{user_id}/toggle-active")
async def admin_toggle_user(user_id: str, _admin: dict = Depends(require_super_admin)):
    from server import db
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    new_state = not target.get("is_active", True)
    await db.users.update_one({"id": user_id}, {"$set": {"is_active": new_state}})
    return {"id": user_id, "is_active": new_state}


@admin_router.get("/devices", response_model=List[Device])
async def admin_list_devices(_admin: dict = Depends(require_super_admin)):
    from server import db
    docs = await db.devices.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs
