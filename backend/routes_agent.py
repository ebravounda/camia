"""Routes for the SmartCam Raspberry Pi agent.

Authentication for agents uses an `Authorization: Agent <api_key>` header.
"""
import io
import os
import secrets
import tarfile
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from models import utcnow, new_id
from auth import get_current_user
from streaming_hub import set_frame as stream_set_frame


router = APIRouter(prefix="/agent", tags=["agent"])


# ---------- Agent auth dep ----------
async def get_current_agent(request: Request) -> dict:
    from server import db
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Agent "):
        raise HTTPException(status_code=401, detail="Agent API key required")
    api_key = auth_header[len("Agent "):].strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="Agent API key vacío")
    device = await db.devices.find_one({"agent_api_key": api_key}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=401, detail="Agent API key inválido")
    return device


# ---------- Schemas ----------
class PairRequest(BaseModel):
    token: str
    hostname: Optional[str] = None
    agent_version: Optional[str] = "0.1.0"
    ip_address: Optional[str] = None


class PairResponse(BaseModel):
    device_id: str
    api_key: str
    api_url: str
    user_id: str
    name: str


class HeartbeatRequest(BaseModel):
    cpu_temp: Optional[float] = None
    cpu_usage: Optional[float] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = None


class CameraReport(BaseModel):
    usb_index: int
    width: Optional[int] = None
    height: Optional[int] = None
    name: Optional[str] = None  # device name from V4L2


class CameraReportRequest(BaseModel):
    cameras: List[CameraReport]


class ThumbnailRequest(BaseModel):
    camera_id: str
    thumbnail_b64: str  # base64 JPEG, small (~100KB max)


class EventReport(BaseModel):
    camera_id: str
    event_type: str = "motion"
    severity: str = "low"
    description: Optional[str] = None
    thumbnail_b64: Optional[str] = None


# ---------- Pairing (no auth) ----------
@router.post("/pair", response_model=PairResponse)
async def pair(payload: PairRequest, request: Request):
    from server import db
    token = (payload.token or "").strip().upper()
    if not token:
        raise HTTPException(status_code=400, detail="Token requerido")
    device = await db.devices.find_one({"pairing_token": token}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Token inválido o no encontrado")

    # Generate a long api_key for the agent
    api_key = f"sca_{secrets.token_urlsafe(32)}"

    update = {
        "agent_api_key": api_key,
        "is_paired": True,
        "status": "online",
        "last_seen": utcnow().isoformat(),
        "hostname": payload.hostname,
        "agent_version": payload.agent_version,
        "ip_address": payload.ip_address or (request.client.host if request.client else None),
    }
    await db.devices.update_one({"id": device["id"]}, {"$set": update})

    # Build api_url from request
    base = str(request.base_url).rstrip("/")
    api_url = f"{base}/api"

    return PairResponse(
        device_id=device["id"],
        api_key=api_key,
        api_url=api_url,
        user_id=device["user_id"],
        name=device["name"],
    )


# ---------- Heartbeat ----------
@router.post("/heartbeat")
async def heartbeat(payload: HeartbeatRequest, device: dict = Depends(get_current_agent)):
    from server import db
    update = {
        "last_seen": utcnow().isoformat(),
        "status": "online",
    }
    if payload.cpu_temp is not None:
        update["cpu_temp"] = payload.cpu_temp
    if payload.cpu_usage is not None:
        update["cpu_usage"] = payload.cpu_usage
    if payload.ip_address:
        update["ip_address"] = payload.ip_address
    if payload.agent_version:
        update["agent_version"] = payload.agent_version
    await db.devices.update_one({"id": device["id"]}, {"$set": update})
    return {"ok": True, "server_time": utcnow().isoformat()}


# ---------- Agent fetches its assigned cameras ----------
@router.get("/cameras")
async def agent_cameras(device: dict = Depends(get_current_agent)):
    from server import db
    cameras = await db.cameras.find(
        {"device_id": device["id"], "user_id": device["user_id"]},
        {"_id": 0, "last_thumbnail": 0},  # don't echo big blobs back
    ).to_list(100)
    return {"cameras": cameras}


# ---------- Agent reports detected USB cameras (informational) ----------
@router.post("/detected-cameras")
async def report_detected(payload: CameraReportRequest, device: dict = Depends(get_current_agent)):
    from server import db
    await db.devices.update_one(
        {"id": device["id"]},
        {"$set": {
            "detected_cameras": [c.dict() for c in payload.cameras],
            "detected_cameras_at": utcnow().isoformat(),
        }},
    )
    return {"received": len(payload.cameras)}


# ---------- Thumbnail upload ----------
MAX_THUMB_B64_LEN = 250_000  # ~180KB after base64

@router.post("/thumbnail")
async def upload_thumbnail(payload: ThumbnailRequest, device: dict = Depends(get_current_agent)):
    from server import db
    if len(payload.thumbnail_b64) > MAX_THUMB_B64_LEN:
        raise HTTPException(status_code=413, detail="Thumbnail demasiado grande")
    cam = await db.cameras.find_one({"id": payload.camera_id, "device_id": device["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no asignada a este dispositivo")
    await db.cameras.update_one(
        {"id": payload.camera_id},
        {"$set": {
            "last_thumbnail": payload.thumbnail_b64,
            "last_thumbnail_at": utcnow().isoformat(),
            "status": "live",
        }},
    )
    return {"ok": True}


# ---------- Event report ----------
@router.post("/event")
async def report_event(payload: EventReport, device: dict = Depends(get_current_agent)):
    from server import db
    if payload.thumbnail_b64 and len(payload.thumbnail_b64) > MAX_THUMB_B64_LEN:
        payload.thumbnail_b64 = payload.thumbnail_b64[:MAX_THUMB_B64_LEN]
    cam = await db.cameras.find_one({"id": payload.camera_id, "device_id": device["id"]}, {"_id": 0})
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no asignada a este dispositivo")
    event_doc = {
        "id": new_id(),
        "user_id": device["user_id"],
        "device_id": device["id"],
        "camera_id": payload.camera_id,
        "camera_name": cam.get("name"),
        "event_type": payload.event_type,
        "severity": payload.severity,
        "description": payload.description,
        "thumbnail_url": f"data:image/jpeg;base64,{payload.thumbnail_b64}" if payload.thumbnail_b64 else None,
        "clip_url": None,
        "created_at": utcnow().isoformat(),
    }
    await db.events.insert_one(event_doc)
    await db.cameras.update_one({"id": payload.camera_id}, {"$set": {"last_event_at": event_doc["created_at"]}})
    event_doc.pop("_id", None)
    return event_doc


# ---------- Download agent (authenticated panel user) ----------
AGENT_DIR = Path("/app/agent")


@router.get("/download")
async def download_agent(user: dict = Depends(get_current_user)):
    if not AGENT_DIR.exists():
        raise HTTPException(status_code=500, detail="Agent files not found on server")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in AGENT_DIR.rglob("*"):
            if any(part in {"__pycache__", ".git", "node_modules"} for part in path.parts):
                continue
            arcname = "smartcam-agent/" + str(path.relative_to(AGENT_DIR))
            tar.add(path, arcname=arcname)
    buf.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="smartcam-agent.tar.gz"'}
    return StreamingResponse(buf, media_type="application/gzip", headers=headers)


# ---------- Live frame upload (raw JPEG) ----------
MAX_FRAME_SIZE = 500_000  # 500KB per frame is enough for 720p MJPEG


@router.post("/frame")
async def upload_frame(
    request: Request,
    x_camera_id: str = Header(..., alias="X-Camera-Id"),
    device: dict = Depends(get_current_agent),
):
    """Agent uploads a single JPEG frame (Content-Type: image/jpeg)."""
    from server import db
    cam = await db.cameras.find_one(
        {"id": x_camera_id, "device_id": device["id"]}, {"_id": 0}
    )
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no asignada a este dispositivo")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Frame vacío")
    if len(body) > MAX_FRAME_SIZE:
        raise HTTPException(status_code=413, detail="Frame demasiado grande")
    stream_set_frame(x_camera_id, body)
    return {"ok": True, "size": len(body)}


# ---------- Background task: mark devices offline if no heartbeat ----------
async def mark_stale_devices_offline(db):
    """Mark devices as offline if last_seen > 90s ago."""
    cutoff = (utcnow() - timedelta(seconds=90)).isoformat()
    await db.devices.update_many(
        {"last_seen": {"$lt": cutoff}, "status": "online"},
        {"$set": {"status": "offline"}},
    )
