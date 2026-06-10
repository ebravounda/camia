"""HTTP client helpers for SmartCam agent → backend."""
from __future__ import annotations

import json
from typing import Optional, List, Dict, Any

import requests


class AgentError(Exception):
    pass


DEFAULT_TIMEOUT = 15


def _auth_headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Agent {api_key}", "Content-Type": "application/json"}


def pair(api_url: str, token: str, hostname: Optional[str] = None,
         ip_address: Optional[str] = None, agent_version: Optional[str] = None) -> Dict[str, Any]:
    """Exchange a one-time pairing token for an api_key + device_id."""
    payload = {"token": token.strip().upper()}
    if hostname:
        payload["hostname"] = hostname
    if ip_address:
        payload["ip_address"] = ip_address
    if agent_version:
        payload["agent_version"] = agent_version
    try:
        r = requests.post(f"{api_url.rstrip('/')}/agent/pair", json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise AgentError(f"network: {e}")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except json.JSONDecodeError:
            detail = r.text
        raise AgentError(f"{r.status_code}: {detail}")
    return r.json()


def heartbeat(api_url: str, api_key: str, **fields) -> None:
    payload = {k: v for k, v in fields.items() if v is not None}
    r = requests.post(f"{api_url.rstrip('/')}/agent/heartbeat", json=payload,
                      headers=_auth_headers(api_key), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()


def get_assigned_cameras(api_url: str, api_key: str) -> List[Dict[str, Any]]:
    r = requests.get(f"{api_url.rstrip('/')}/agent/cameras",
                     headers=_auth_headers(api_key), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json().get("cameras", [])


def report_detected_cameras(api_url: str, api_key: str, cameras: List[Dict[str, Any]]) -> None:
    r = requests.post(f"{api_url.rstrip('/')}/agent/detected-cameras",
                      json={"cameras": cameras},
                      headers=_auth_headers(api_key), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()


def upload_thumbnail(api_url: str, api_key: str, camera_id: str, b64: str) -> None:
    r = requests.post(f"{api_url.rstrip('/')}/agent/thumbnail",
                      json={"camera_id": camera_id, "thumbnail_b64": b64},
                      headers=_auth_headers(api_key), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()


# Shared session for live-frame streaming (keep-alive critical for 5fps).
_stream_session: Optional[requests.Session] = None


def _get_stream_session() -> requests.Session:
    global _stream_session
    if _stream_session is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=4)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _stream_session = s
    return _stream_session


def upload_live_frame(api_url: str, api_key: str, camera_id: str, jpeg_bytes: bytes) -> None:
    """POST raw JPEG bytes for live streaming. Keep-alive HTTP session."""
    session = _get_stream_session()
    headers = {
        "Authorization": f"Agent {api_key}",
        "Content-Type": "image/jpeg",
        "X-Camera-Id": camera_id,
    }
    r = session.post(
        f"{api_url.rstrip('/')}/agent/frame",
        data=jpeg_bytes,
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()


def upload_audio(api_url: str, api_key: str, camera_id: str, pcm_bytes: bytes) -> None:
    """POST raw PCM s16le mono 16kHz audio chunk."""
    session = _get_stream_session()
    headers = {
        "Authorization": f"Agent {api_key}",
        "Content-Type": "audio/L16",
        "X-Camera-Id": camera_id,
    }
    r = session.post(
        f"{api_url.rstrip('/')}/agent/audio",
        data=pcm_bytes,
        headers=headers,
        timeout=5,
    )
    r.raise_for_status()


def analyze_frame(api_url: str, api_key: str, camera_id: str, jpeg_bytes: bytes) -> list:
    """POST a JPEG to backend for YOLO analysis; returns list of detections."""
    session = _get_stream_session()
    headers = {
        "Authorization": f"Agent {api_key}",
        "Content-Type": "image/jpeg",
        "X-Camera-Id": camera_id,
    }
    r = session.post(
        f"{api_url.rstrip('/')}/agent/analyze",
        data=jpeg_bytes,
        headers=headers,
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("detections", [])


def report_event(api_url: str, api_key: str, camera_id: str, event_type: str = "motion",
                 severity: str = "low", description: Optional[str] = None,
                 thumbnail_b64: Optional[str] = None) -> None:
    payload = {
        "camera_id": camera_id,
        "event_type": event_type,
        "severity": severity,
        "description": description,
        "thumbnail_b64": thumbnail_b64,
    }
    r = requests.post(f"{api_url.rstrip('/')}/agent/event",
                      json=payload, headers=_auth_headers(api_key), timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
