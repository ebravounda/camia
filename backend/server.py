"""SmartCam SaaS - FastAPI main server."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from auth import router as auth_router, seed_admin
from routes_app import router as app_router, admin_router
from routes_billing import router as billing_router, stripe_webhook_handler
from routes_agent import router as agent_router, mark_stale_devices_offline
import clip_recorder


# MongoDB
mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]


# FastAPI
app = FastAPI(title="SmartCam SaaS API", version="1.0.0")
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "SmartCam SaaS", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "healthy"}


# Mount sub-routers
api_router.include_router(auth_router)
api_router.include_router(app_router)
api_router.include_router(admin_router)
api_router.include_router(billing_router)
api_router.include_router(agent_router)


# Stripe webhook (public, no auth)
@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    return await stripe_webhook_handler(request)


app.include_router(api_router)

# Serve micro-event clips (MP4)
app.mount("/api/clips", StaticFiles(directory=str(clip_recorder.CLIPS_DIR)), name="clips")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smartcam")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.devices.create_index("id", unique=True)
    await db.devices.create_index("pairing_token")
    await db.devices.create_index("agent_api_key")
    await db.devices.create_index("user_id")
    await db.cameras.create_index("id", unique=True)
    await db.cameras.create_index("user_id")
    await db.cameras.create_index("device_id")
    await db.events.create_index([("user_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("session_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await seed_admin(db)
    # Mark stale devices offline at startup
    await mark_stale_devices_offline(db)
    # Start clip retention cleanup loop (purge >7 days every hour)
    import asyncio as _asyncio
    _asyncio.create_task(clip_recorder.retention_loop())
    logger.info("SmartCam SaaS API started; admin seeded.")


@app.on_event("shutdown")
async def shutdown():
    mongo_client.close()
