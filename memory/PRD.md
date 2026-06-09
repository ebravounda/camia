# SmartCam SaaS - PRD

## Problem Statement (original, ES)
Plataforma SaaS multiusuario que conecta cámaras USB en una Raspberry Pi con un panel web. La IA detecta personas, caras, objetos y comportamientos sospechosos, guarda los videos por 7 días en Google Drive y envía alertas por WhatsApp.

Componentes:
- Agente Raspberry Pi (Python + OpenCV + YOLOv8n + face_recognition)
- Panel Web (React + TypeScript + TailwindCSS, dark mode estilo Linear/Vercel)
- Backend FastAPI + MongoDB + WebSockets
- Integraciones: Google Drive (OAuth), Twilio WhatsApp, Stripe

## User Personas
- **Dueños de pequeños negocios / tiendas**: hasta 4 cámaras, monitoreo nocturno
- **Hogares particulares**: vigilancia perimetral y reconocimiento de caras conocidas
- **Super Admin (plataforma)**: gestiona usuarios, dispositivos y planes

## Tech Stack
- Frontend: React 19 + Tailwind 3 + Shadcn UI + lucide-react + sonner
- Backend: FastAPI + Motor + bcrypt + PyJWT + emergentintegrations (Stripe)
- Agente Pi: Python 3 + requests + opencv-python(-headless)
- DB: MongoDB
- Auth (panel): JWT custom + Emergent Google Auth
- Auth (agente): API key tipo `sca_*` en header `Authorization: Agent <key>`
- Pagos: Stripe Checkout (suscripción mensual)
- Idioma UI: Español

## Architecture decisions
- DB IDs: UUID custom en campo `id` (no usar `_id` Mongo)
- Datetimes: timezone-aware UTC, almacenadas en ISO string
- Auth tokens panel: cookies httpOnly + fallback Bearer (localStorage)
- Pairing token format: `XXXX-XXXX-XXXX` (12 hex uppercase + 2 guiones = 14 chars)
- Agente API key: `sca_` + 32 chars urlsafe (~43 chars)
- Stripe: `emergentintegrations.payments.stripe.checkout`, key `sk_test_emergent` del entorno

## Phase 1 - Implemented (2026-02)
- [x] Auth multiusuario JWT (register/login/logout/me) con bcrypt
- [x] Emergent Google Auth
- [x] Seed idempotente super_admin (admin@smartcam.com / SmartCam2026!)
- [x] Modelos Mongo + índices
- [x] CRUD Devices / Cameras / Events
- [x] /dashboard/stats
- [x] Super Admin: stats, list users, toggle active, list devices
- [x] Stripe Checkout (planes Free $0 / Pro $19 / Enterprise $49)
- [x] UI completa en español dark mode (Outfit + Manrope + JetBrains Mono)
- [x] 34 backend tests pytest pasando

## Phase 2 - Implemented (2026-02)
- [x] Token de emparejamiento formato `XXXX-XXXX-XXXX`
- [x] Endpoint `POST /api/agent/pair` (sin auth, valida token, genera api_key)
- [x] Endpoint `POST /api/agent/heartbeat` (auth Agent header) - CPU temp/usage/IP/agent_version
- [x] Endpoint `GET /api/agent/cameras` - cámaras asignadas al device
- [x] Endpoint `POST /api/agent/detected-cameras` - reporte de /dev/video*
- [x] Endpoint `POST /api/agent/thumbnail` - upload base64 JPEG (límite 250KB)
- [x] Endpoint `POST /api/agent/event` - reporte de evento con thumbnail
- [x] Endpoint `GET /api/agent/download` - tar.gz del agente
- [x] Agente Python (`/app/agent/`):
  - `smartcam_agent/agent.py` - CLI `pair` y `run` con threading
  - `smartcam_agent/client.py` - HTTP client
  - `smartcam_agent/heartbeat.py` - lectura /sys/class/thermal y /proc/stat
  - `smartcam_agent/camera_loop.py` - scan USB, thumbnails, motion detection con OpenCV
  - `install.sh` - instalador apt + venv --system-site-packages + systemd
  - `smartcam-agent.service` - systemd unit
  - `README.md` - guía de instalación paso a paso
- [x] Frontend `/devices`: botón "Descargar agente", grid CPU °C / CPU % / IP en cards paired
- [x] Frontend `/cameras`: render de last_thumbnail como `<img data:image/jpeg;base64,...>`
- [x] Frontend Dashboard: LiveTile usa last_thumbnail de cámaras reales + polling cada 30s
- [x] 57 backend tests pytest pasando (Fase 1 + Fase 2)

## Phase 3 - Streaming en vivo (1-4 cámaras)
- [ ] WebRTC con aiortc o MJPEG sobre WebSocket
- [ ] LiveTile component conecta al stream del agente

## Phase 4 - Grabación + Google Drive + rotación 7 días
- [ ] OAuth Google Drive (settings.connect_gdrive)
- [ ] Agente sube clips a /SmartCam/{camara}/{YYYY-MM-DD}/{HH-MM-SS}.mp4
- [ ] Cron de limpieza >7 días

## Phase 5 - IA (YOLO + facial + sospechoso) + Timeline real
- [ ] YOLOv8n en el agente
- [ ] face_recognition / InsightFace + base "caras conocidas"
- [ ] Clasificador de eventos sospechosos
- [ ] Eventos persistidos en MongoDB con thumbnail_url + clip_url

## Phase 6 - Alertas WhatsApp (Twilio)
- [ ] Integración Twilio
- [ ] Configuración del número en /settings
- [ ] Trigger en eventos suspicious

## Phase 7 - Pulido + métricas + Super Admin completo
- [ ] Logs y métricas globales (charts en admin)
- [ ] Gestión de planes desde admin
- [ ] Onboarding wizard

## Backlog / Improvements
- [ ] P1: Invalidar pairing_token tras primer pair exitoso (actualmente solo se invalida vía Regenerar)
- [ ] P1: /api/agent/event devuelve 413 en thumbnail oversize en vez de truncar (consistencia con /thumbnail)
- [ ] P2: CORS_ORIGINS explícito en producción
- [ ] P2: i18n EN/ES
- [ ] P2: Cache del tar.gz de /agent/download
- [ ] P2: TTL para detected_cameras + métricas históricas
