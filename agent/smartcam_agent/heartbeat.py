"""Heartbeat helpers: gather CPU temp/usage on Raspberry Pi and send."""
from __future__ import annotations

import os
import time
from typing import Optional

from . import client


def cpu_temperature() -> Optional[float]:
    """Read Pi's CPU temperature in °C. Returns None if unavailable."""
    # Standard thermal zone (works on Raspberry Pi OS)
    path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(path) as f:
            raw = f.read().strip()
        return round(int(raw) / 1000.0, 1)
    except (OSError, ValueError):
        pass
    # vcgencmd fallback (if available)
    try:
        import subprocess
        out = subprocess.check_output(["vcgencmd", "measure_temp"], timeout=2).decode()
        # "temp=42.8'C\n"
        val = out.split("=")[1].split("'")[0]
        return float(val)
    except Exception:
        return None


# We sample CPU usage by reading /proc/stat between calls.
_prev_cpu = None  # (idle, total)


def cpu_usage_percent() -> Optional[float]:
    """Return cumulative CPU usage % across all cores since last call."""
    global _prev_cpu
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = [float(x) for x in line.split()[1:]]
        idle = parts[3] + parts[4]  # idle + iowait
        total = sum(parts)
    except (OSError, ValueError, IndexError):
        return None
    if _prev_cpu is None:
        _prev_cpu = (idle, total)
        return None
    delta_idle = idle - _prev_cpu[0]
    delta_total = total - _prev_cpu[1]
    _prev_cpu = (idle, total)
    if delta_total <= 0:
        return None
    usage = 100.0 * (1.0 - (delta_idle / delta_total))
    return round(max(0.0, min(100.0, usage)), 1)


def send_heartbeat(api_url: str, api_key: str, agent_version: str = "0.2.0",
                   ip: Optional[str] = None) -> None:
    client.heartbeat(
        api_url, api_key,
        cpu_temp=cpu_temperature(),
        cpu_usage=cpu_usage_percent(),
        ip_address=ip,
        agent_version=agent_version,
    )
