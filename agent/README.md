# SmartCam Agent — Raspberry Pi

Agente Python para Raspberry Pi (3B+ / 4 / 5) que captura cámaras USB, detecta movimiento y se comunica con el panel **SmartCam SaaS**.

## Requisitos en la Pi

- Raspberry Pi 3B+, 4 o 5
- Raspberry Pi OS 64-bit (Bookworm) recomendado
- Acceso a internet
- 1–4 cámaras USB enchufadas (`/dev/video0`, `/dev/video1`, …)

## Instalación en 5 minutos

### 1) Conéctate por SSH a tu Pi

```bash
ssh pi@<ip-de-la-pi>
```

### 2) Crea el dispositivo en el panel y obtén tu token

1. Inicia sesión en SmartCam SaaS.
2. Ve a **Raspberry Pi** → **Nueva Raspberry**.
3. Copia el **token de emparejamiento** (formato `XXXX-XXXX-XXXX`).

### 3) Descarga el agente desde el panel

Desde la página **Raspberry Pi** pulsa **"Descargar agente"** (botón superior).
Esto te da `smartcam-agent.tar.gz`. Copia el archivo a tu Pi (por ejemplo con `scp`):

```bash
scp smartcam-agent.tar.gz pi@<ip-de-la-pi>:~
```

Alternativa: clona este repo dentro de la Pi (`git clone ...`).

### 4) Instala

En la Pi:

```bash
cd ~
tar -xzf smartcam-agent.tar.gz
cd smartcam-agent

sudo bash install.sh \
  --token XXXX-XXXX-XXXX \
  --api-url https://tu-panel.com/api
```

El instalador:
- instala `python3`, `python3-opencv`, `v4l-utils`
- copia el agente a `/opt/smartcam-agent/`
- empareja tu Pi con el panel usando el token
- crea el servicio **systemd** `smartcam-agent` y lo arranca al boot

### 5) Verifica que está corriendo

```bash
sudo systemctl status smartcam-agent
sudo journalctl -u smartcam-agent -f
```

En el panel deberías ver el dispositivo como **online** con CPU temp / uso al cabo de 30s.

### 6) Configura tus cámaras desde el panel

1. Conecta tus cámaras USB a la Pi.
2. Ve a **Cámaras** → **Nueva cámara**. Selecciona la Raspberry y el índice USB (0, 1, 2 o 3 según `/dev/video*`).
3. El agente las detectará en el siguiente ciclo (≤ 60 s), capturará thumbnails y empezará a detectar movimiento.

## Comandos útiles

```bash
# Logs en vivo
sudo journalctl -u smartcam-agent -f

# Reiniciar
sudo systemctl restart smartcam-agent

# Listar /dev/video*
v4l2-ctl --list-devices

# Probar manualmente (sin servicio)
sudo /opt/smartcam-agent/venv/bin/python -m smartcam_agent.agent run
```

## Variables de entorno opcionales

| Variable | Default | Descripción |
|---|---|---|
| `SMARTCAM_CONFIG` | `/etc/smartcam/config.json` | Ruta al config |
| `SMARTCAM_THUMB_INTERVAL` | `300` | Segundos entre thumbnails al panel |
| `SMARTCAM_MOTION_FPS` | `4` | FPS de análisis de movimiento |
| `SMARTCAM_MOTION_AREA` | `1500` | Píxeles mínimos para evento de movimiento |
| `SMARTCAM_MOTION_COOLDOWN` | `30` | Segundos entre eventos consecutivos por cámara |

## Re-emparejar / cambiar de cuenta

Si quieres mover la Pi a otra cuenta o regenerar el token:

```bash
sudo rm /etc/smartcam/config.json
sudo /opt/smartcam-agent/venv/bin/python -m smartcam_agent.agent \
  pair --token NUEVO-TOKEN-AQUI --api-url https://tu-panel.com/api
sudo systemctl restart smartcam-agent
```

## Notas de rendimiento

- **Pi 3B+ (32-bit no recomendado)**: solo detección de movimiento. Limita a 1–2 cámaras.
- **Pi 4 / Pi 5**: hasta 4 cámaras simultáneas + Fase 5 (IA YOLOv8n).
- Las cámaras USB con resolución alta (1080p) consumen mucho CPU.
  Recomendado: cámaras USB **720p o 480p** para 4 streams simultáneos.

## Desinstalar

```bash
sudo systemctl disable --now smartcam-agent
sudo rm -rf /etc/systemd/system/smartcam-agent.service /opt/smartcam-agent /etc/smartcam
sudo systemctl daemon-reload
```

## Privacidad

Solo se sube al panel:
- Heartbeat (CPU temp, uso, IP)
- Thumbnails JPEG comprimidos (≤ 480px de ancho) cada 5 min
- Thumbnails de eventos de movimiento

El video en vivo y los clips completos viven en tu Pi (Fase 3) y/o en tu Google Drive (Fase 4).
