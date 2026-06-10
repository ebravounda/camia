"""SmartCam Agent - Raspberry Pi side.

Runs as a long-lived process. Responsibilities:
  - Pair with the SmartCam backend using a pairing token (one-time).
  - Send periodic heartbeats (CPU temp, usage, IP).
  - Detect available USB cameras (/dev/video*).
  - For each assigned camera: capture thumbnails + run simple motion detection.
  - Upload thumbnails and report motion events to the backend.

Usage:
    sudo python3 -m smartcam_agent.agent pair --token XXXX-XXXX-XXXX --api-url https://your-app.com/api
    python3 -m smartcam_agent.agent run

Or via systemd: see smartcam-agent.service
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from . import client
from . import heartbeat as hb
from . import camera_loop
from . import audio_loop

AGENT_VERSION = "0.3.0"
DEFAULT_CONFIG_PATH = Path(os.environ.get("SMARTCAM_CONFIG", "/etc/smartcam/config.json"))


def _load_config(path: Path) -> dict:
    if not path.exists():
        print(f"[agent] config file not found at {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text())


def _save_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _local_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def cmd_pair(args: argparse.Namespace) -> int:
    token = (args.token or os.environ.get("SMARTCAM_TOKEN", "")).strip().upper()
    api_url = (args.api_url or os.environ.get("SMARTCAM_API_URL", "")).rstrip("/")
    if not token or not api_url:
        print("[agent] --token and --api-url are required (or set SMARTCAM_TOKEN / SMARTCAM_API_URL)", file=sys.stderr)
        return 2

    hostname = socket.gethostname()
    ip = _local_ip()
    print(f"[agent] pairing host={hostname} ip={ip} ...")
    try:
        resp = client.pair(api_url, token, hostname=hostname, ip_address=ip, agent_version=AGENT_VERSION)
    except client.AgentError as e:
        print(f"[agent] pairing failed: {e}", file=sys.stderr)
        return 1

    cfg = {
        "device_id": resp["device_id"],
        "api_key": resp["api_key"],
        # Use the api_url the user provided (the one from the server may be an internal URL)
        "api_url": api_url,
        "name": resp.get("name"),
        "agent_version": AGENT_VERSION,
    }
    _save_config(args.config, cfg)
    print(f"[agent] paired successfully. device_id={cfg['device_id']} name='{cfg.get('name')}'.")
    print(f"[agent] config written to {args.config}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load_config(args.config)
    api_url = cfg["api_url"]
    api_key = cfg["api_key"]
    device_id = cfg["device_id"]
    print(f"[agent] starting (device_id={device_id}, version={AGENT_VERSION})")

    stop_event = threading.Event()

    def heartbeat_thread():
        while not stop_event.is_set():
            try:
                hb.send_heartbeat(api_url, api_key, agent_version=AGENT_VERSION, ip=_local_ip())
            except Exception as e:
                print(f"[agent][heartbeat] error: {e}", file=sys.stderr)
            stop_event.wait(30)

    def discover_thread():
        while not stop_event.is_set():
            try:
                detected = camera_loop.scan_usb_cameras()
                client.report_detected_cameras(api_url, api_key, detected)
            except Exception as e:
                print(f"[agent][discover] error: {e}", file=sys.stderr)
            stop_event.wait(60)

    threads = [
        threading.Thread(target=heartbeat_thread, name="hb", daemon=True),
        threading.Thread(target=discover_thread, name="discover", daemon=True),
        threading.Thread(target=camera_loop.run_camera_workers,
                         args=(api_url, api_key, stop_event), name="cams", daemon=True),
        threading.Thread(target=audio_loop.run_audio_workers,
                         args=(api_url, api_key, stop_event), name="audio", daemon=True),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[agent] stopping...")
        stop_event.set()
        for t in threads:
            t.join(timeout=5)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="smartcam-agent", description="SmartCam Raspberry Pi agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to config JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pair = sub.add_parser("pair", help="Pair this Pi with a SmartCam account using a token")
    p_pair.add_argument("--token", required=False, help="Pairing token from the panel (XXXX-XXXX-XXXX)")
    p_pair.add_argument("--api-url", required=False, help="Backend API URL, e.g. https://your-app.com/api")
    p_pair.set_defaults(func=cmd_pair)

    p_run = sub.add_parser("run", help="Run the agent main loop")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
