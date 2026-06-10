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

## Phase 3 - Streaming en vivo (1-4 cámaras) — Implemented (2026-02)
- [x] WebSocket binary frame streaming (`/api/ws/cameras/{id}/stream`) ultra-low latency (~100-200ms)
- [x] HTTP MJPEG multipart fallback (`/api/cameras/{id}/stream.mjpg`)
- [x] Frontend `<canvas>` render con `createImageBitmap` + FPS estimator + snapshot/fullscreen/reload controls
- [x] Auto-reconnect a los 2s si se cae la WS

## Phase 4 - Grabación + rotación 7 días — Partial (2026-06)
- [x] Micro-clips de 5s (2s pre + 3s post) generados automáticamente para TODOS los eventos
- [x] Rolling buffer en RAM por cámara (video + audio) en `/app/backend/clip_recorder.py`
- [x] **Encoding H.264 + AAC con PyAV/ffmpeg** (faststart para reproducción móvil)
- [x] Servidos vía StaticFiles en `/api/clips/{event_id}.mp4`
- [x] Loop de retention cada 1h purga clips > 7 días
- [x] Reproductor `<video controls autoplay>` en modal de Eventos (con audio si lo hay)
- [ ] P0: OAuth Google Drive (settings.connect_gdrive) + subida de clips a /SmartCam/{cam}/{YYYY-MM-DD}/...

## Phase 4.5 - HD/FHD + Audio (2026-06)
- [x] Selector de resolución **SD/HD/FHD** por cámara (UI en /cameras, PATCH /api/cameras/{id})
- [x] Agente lee la resolución desde `/agent/cameras` y aplica `cv2.CAP_PROP_FRAME_WIDTH/HEIGHT`
- [x] Stream pasa la resolución capturada tal cual (`STREAM_MAX_WIDTH=0` por defecto)
- [x] **Audio capture** en el Pi: `audio_loop.py` con `arecord` subprocess (PCM s16le mono 16 kHz)
- [x] Auto-detección de micrófono ALSA (skip si no hay `arecord -l` capture device)
- [x] Endpoint `POST /api/agent/audio` recibe chunks (~200ms = 6.4KB) y los pushea al buffer + WS
- [x] Protocolo WS multiplexado: 1-byte marker `0x01`=video JPEG, `0x02`=audio PCM
- [x] Frontend `CameraLive.jsx` con **Web Audio API** decodifica PCM con jitter buffer ~150ms
- [x] Control de mute/unmute en el reproductor live (gesto de usuario respeta autoplay policy)
- [x] Eventos guardan `clip_has_audio: bool` para mostrar el badge correcto en el modal

## Phase 5 - IA (YOLO + facial + sospechoso) + Timeline — Partial
- [x] YOLOv8n en el backend (`ai_service.py`, torch-cpu + onnxruntime, ~350ms/frame)
- [x] Endpoint `/api/agent/analyze` con auto-creación de eventos rate-limited 60s
- [x] Eventos persistidos en MongoDB con thumbnail_url + clip_url
- [x] Frontend Timeline con filtros + modal de detalle con clip player
- [x] Face DETECTION en el agente (Haar cascade ligero para Pi 3B+)
- [ ] P1: Face RECOGNITION real (embeddings) contra galería `/faces`
- [ ] P1: Clasificador de eventos sospechosos (lógica de zonas + comportamiento)

## Phase UI Polish (2026-06)
- [x] Refactor "Brutalist Editorial": lima eléctrico #C8FF00, Bricolage Grotesque, bordes filosos
- [x] Framer Motion: stat cards staggered, eventos fade-up, AppShell fade+slide entre páginas
- [x] Mobile responsive con Sheet drawer
- [x] Bug fix: parpadeo en sidebar al navegar (NavRow estaba definido dentro del componente, causaba unmount/remount cada render)

## Phase 6 - Alertas WhatsApp (Twilio)
- [ ] P1: Integración Twilio
- [ ] P1: Configuración del número en /settings
- [ ] P1: Trigger en eventos suspicious

## Phase 7 - Pulido + métricas + Super Admin completo
- [ ] P2: Logs y métricas globales (charts en admin)
- [ ] P2: Gestión de planes desde admin
- [ ] P2: Onboarding wizard

## Backlog / Improvements
- [ ] P1: Invalidar pairing_token tras primer pair exitoso (actualmente solo se invalida vía Regenerar)
- [ ] P1: /api/agent/event devuelve 413 en thumbnail oversize en vez de truncar (consistencia con /thumbnail)
- [ ] P2: CORS_ORIGINS explícito en producción
- [ ] P2: i18n EN/ES
- [ ] P2: Cache del tar.gz de /agent/download
- [ ] P2: TTL para detected_cameras + métricas históricas
- [ ] P2: Browser-friendly H.264 (faststart) en lugar de mp4v para mejor compat móvil
