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
- DB: MongoDB
- Auth: JWT custom (email/password) + Emergent-managed Google Auth
- Pagos: Stripe Checkout (suscripción mensual)
- Idioma UI: Español

## Architecture decisions
- DB IDs: UUID custom en campo `id` (no usar `_id` Mongo)
- Datetimes: timezone-aware UTC, almacenadas en ISO string
- Auth tokens: cookies httpOnly + fallback Bearer (localStorage)
- Stripe: `emergentintegrations.payments.stripe.checkout`, key `sk_test_emergent` del entorno

## Phase 1 - Implemented (2026-02)
- [x] Auth multiusuario JWT (register/login/logout/me) con bcrypt
- [x] Emergent Google Auth (endpoint /auth/google/session, AuthCallback en hash)
- [x] Seed idempotente super_admin (admin@smartcam.com / SmartCam2026!)
- [x] Modelos Mongo: users, devices, cameras, events, payment_transactions, user_sessions (con índices)
- [x] CRUD Devices (con pairing_token + regenerate)
- [x] CRUD Cameras
- [x] Endpoint GET /events con filtros (event_type, camera_id)
- [x] Endpoint /dashboard/stats
- [x] Super Admin: stats, list users, toggle user active, list devices
- [x] Stripe Checkout: /billing/checkout, /billing/status/{id}, /webhook/stripe
- [x] 3 planes hardcoded (Free $0, Pro $19, Enterprise $49)
- [x] UI completa en español, dark mode navy/charcoal:
  - Landing (hero + features + CTA)
  - Login / Register (con botón Google)
  - Dashboard (4 stat cards + grid 2x2 placeholders + timeline lateral)
  - Devices (diálogo crear, copiar/regenerar/eliminar token)
  - Cameras (diálogo crear con select device + usb_index)
  - Events (filtros por tipo)
  - Pricing (3 planes + Stripe redirect)
  - Settings (cuenta, suscripción, GDrive/WhatsApp placeholders)
  - Admin Panel (stats + tablas usuarios + dispositivos)
  - Billing Success (poll status)
- [x] Sidebar con link Super Admin condicional + logout
- [x] data-testid en todos los elementos interactivos
- [x] Tests pytest (34/34) + tests frontend manuales pasando

## Phase 2 - Raspberry Pi pairing + agent
- [ ] Agente Python básico (cli) que se empareja vía POST /api/devices/pair {token}
- [ ] Heartbeat: POST /api/devices/{id}/heartbeat (cpu_temp, cpu_usage, ip)
- [ ] WS notification cuando device cambia status

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
- [ ] P1: silenciar 401 noise en /me cuando no hay token (DONE en post-test)
- [ ] P1: harden pairing_token (token_hex(6))
- [ ] P2: CORS_ORIGINS explícito en producción
- [ ] P2: i18n EN/ES

## Files map (Phase 1)
- /app/backend/server.py - main FastAPI app + startup (seed_admin, índices)
- /app/backend/auth.py - JWT utils + auth router + Google session
- /app/backend/models.py - Pydantic models
- /app/backend/routes_app.py - devices/cameras/events/dashboard/admin
- /app/backend/routes_billing.py - Stripe checkout/status/webhook
- /app/frontend/src/App.js - routing + Auth callback handler
- /app/frontend/src/contexts/AuthContext.jsx - global auth state
- /app/frontend/src/components/{Sidebar,AppShell,ProtectedRoute}.jsx
- /app/frontend/src/pages/* - todas las páginas
- /app/frontend/src/lib/api.js - axios + formatApiError
