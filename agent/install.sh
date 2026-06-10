#!/usr/bin/env bash
# SmartCam Agent installer for Raspberry Pi OS (64-bit Bookworm).
# Tested on Raspberry Pi 3B+ and Raspberry Pi 4.
#
# Usage:
#   sudo bash install.sh
#   sudo bash install.sh --token XXXX-XXXX-XXXX --api-url https://your-app.com/api
#
set -euo pipefail

INSTALL_DIR="/opt/smartcam-agent"
CONFIG_DIR="/etc/smartcam"
CONFIG_FILE="${CONFIG_DIR}/config.json"
SERVICE_NAME="smartcam-agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SERVICE_USER="root"   # needs access to /dev/video* (or add user to 'video' group)

TOKEN=""
API_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --token) TOKEN="$2"; shift 2;;
    --api-url) API_URL="$2"; shift 2;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "This installer must be run as root (sudo)." >&2
  exit 1
fi

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
echo ">>> SmartCam Agent installer"
echo ">>> Source dir: ${SCRIPT_DIR}"
echo ">>> Install dir: ${INSTALL_DIR}"

# 1) Detect architecture
ARCH="$(uname -m)"
echo ">>> Detected arch: ${ARCH}"

# 2) Apt deps
echo ">>> Installing system packages..."
apt-get update -y
apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv python3-requests v4l-utils alsa-utils ca-certificates

# python3-opencv from apt is the safest path on Pi (uses optimised system libs)
if ! python3 -c "import cv2" >/dev/null 2>&1; then
  echo ">>> Installing python3-opencv (system) ..."
  apt-get install -y --no-install-recommends python3-opencv || true
fi

# 3) Copy agent files
echo ">>> Copying agent to ${INSTALL_DIR} ..."
mkdir -p "${INSTALL_DIR}"
cp -r "${SCRIPT_DIR}/smartcam_agent" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

# 4) Create venv with system site-packages (so it can reuse apt python3-opencv)
if [[ ! -d "${INSTALL_DIR}/venv" ]]; then
  echo ">>> Creating Python venv (with system-site-packages) ..."
  python3 -m venv --system-site-packages "${INSTALL_DIR}/venv"
fi
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
# Install requests only; opencv comes from the system to avoid building on Pi
"${INSTALL_DIR}/venv/bin/pip" install requests>=2.31.0

# If OpenCV is still missing, try pip headless (slow on 3B+)
if ! "${INSTALL_DIR}/venv/bin/python" -c "import cv2" >/dev/null 2>&1; then
  echo ">>> Falling back to opencv-python-headless from pip (may take several minutes) ..."
  "${INSTALL_DIR}/venv/bin/pip" install opencv-python-headless
fi

# 5) Pair (if token & api-url provided)
mkdir -p "${CONFIG_DIR}"
chmod 700 "${CONFIG_DIR}"

if [[ -n "${TOKEN}" && -n "${API_URL}" ]]; then
  echo ">>> Pairing with backend ..."
  "${INSTALL_DIR}/venv/bin/python" -m smartcam_agent.agent --config "${CONFIG_FILE}" \
    pair --token "${TOKEN}" --api-url "${API_URL}"
else
  echo ">>> No --token/--api-url passed; you can run pairing manually later:"
  echo "    sudo ${INSTALL_DIR}/venv/bin/python -m smartcam_agent.agent --config ${CONFIG_FILE} pair --token XXXX-XXXX-XXXX --api-url https://your-app.com/api"
fi

# 6) Install systemd service
echo ">>> Installing systemd service ${SERVICE_NAME}..."
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=SmartCam Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PYTHONPATH=${INSTALL_DIR}
Environment=SMARTCAM_CONFIG=${CONFIG_FILE}
ExecStart=${INSTALL_DIR}/venv/bin/python -m smartcam_agent.agent --config ${CONFIG_FILE} run
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

if [[ -f "${CONFIG_FILE}" ]]; then
  systemctl restart "${SERVICE_NAME}.service"
  echo ">>> Service started. Logs:  sudo journalctl -u ${SERVICE_NAME} -f"
else
  echo ">>> Service installed but NOT started (no config yet)."
  echo ">>> After pairing, run:  sudo systemctl start ${SERVICE_NAME}"
fi

echo ">>> Done."
