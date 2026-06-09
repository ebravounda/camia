"""Authentication utilities and routes for SmartCam SaaS."""
import os
import secrets
import bcrypt
import jwt
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from models import (
    UserCreate, UserLogin, UserPublic, AuthResponse, MessageResponse, utcnow, new_id
)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MIN = 60 * 24 * 7  # 7 days for SaaS convenience


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL_MIN),
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _user_to_public(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "email": doc["email"],
        "name": doc["name"],
        "role": doc.get("role", "user"),
        "auth_provider": doc.get("auth_provider", "password"),
        "avatar_url": doc.get("avatar_url"),
        "subscription_plan": doc.get("subscription_plan", "free"),
        "subscription_status": doc.get("subscription_status", "inactive"),
        "is_active": doc.get("is_active", True),
        "created_at": doc["created_at"],
    }


def _set_cookies(response: Response, access_token: str, session_token: Optional[str] = None):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=ACCESS_TOKEN_TTL_MIN * 60,
        path="/",
    )
    if session_token:
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60,
            path="/",
        )


async def get_current_user(request: Request) -> dict:
    """Dependency to extract current user from JWT (cookie or Bearer) or session_token (Google)."""
    from server import db

    # 1) Try JWT access_token from cookie or Authorization header
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if token:
        try:
            payload = jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") == "access":
                user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
                if user and user.get("is_active", True):
                    return user
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass

    # 2) Try session_token cookie (Google auth path)
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]

    if session_token:
        session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
        if session:
            expires_at = session.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and expires_at >= datetime.now(timezone.utc):
                user = await db.users.find_one({"id": session["user_id"]}, {"_id": 0})
                if user and user.get("is_active", True):
                    return user

    raise HTTPException(status_code=401, detail="No autenticado")


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: requiere super_admin")
    return user


# ============== ROUTER ==============
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: UserCreate, response: Response):
    from server import db
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Este email ya está registrado")

    user_id = new_id()
    doc = {
        "id": user_id,
        "email": email,
        "name": payload.name.strip(),
        "password_hash": hash_password(payload.password),
        "role": "user",
        "auth_provider": "password",
        "avatar_url": None,
        "subscription_plan": "free",
        "subscription_status": "inactive",
        "is_active": True,
        "stripe_customer_id": None,
        "google_drive_connected": False,
        "whatsapp_number": None,
        "created_at": utcnow().isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email, "user")
    _set_cookies(response, token)
    return {"user": _user_to_public(doc), "access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserLogin, response: Response):
    from server import db
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Cuenta deshabilitada")

    token = create_access_token(user["id"], user["email"], user.get("role", "user"))
    _set_cookies(response, token)
    return {"user": _user_to_public(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, response: Response):
    from server import db
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"message": "Sesión cerrada"}


@router.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return _user_to_public(user)


# ===== Emergent Google Auth =====
class GoogleSessionPayload(BaseModel):
    session_id: str


@router.post("/google/session", response_model=AuthResponse)
async def google_session(payload: GoogleSessionPayload, response: Response):
    """Exchange Emergent session_id for our session_token & user."""
    from server import db
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": payload.session_id},
            )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="session_id inválido")
        data = r.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="No se pudo contactar al proveedor de auth")

    email = (data.get("email") or "").lower().strip()
    name = data.get("name") or email.split("@")[0]
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=502, detail="Respuesta de auth incompleta")

    user = await db.users.find_one({"email": email})
    if not user:
        user_id = new_id()
        user = {
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": None,
            "role": "user",
            "auth_provider": "google",
            "avatar_url": picture,
            "subscription_plan": "free",
            "subscription_status": "inactive",
            "is_active": True,
            "stripe_customer_id": None,
            "google_drive_connected": False,
            "whatsapp_number": None,
            "created_at": utcnow().isoformat(),
        }
        await db.users.insert_one(user)
    else:
        # Update avatar / name if changed
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"avatar_url": picture or user.get("avatar_url"), "name": name or user.get("name")}},
        )

    # Persist session_token in db
    await db.user_sessions.update_one(
        {"session_token": session_token},
        {"$set": {
            "user_id": user["id"],
            "session_token": session_token,
            "expires_at": (utcnow() + timedelta(days=7)).isoformat(),
            "created_at": utcnow().isoformat(),
        }},
        upsert=True,
    )

    # Also issue our JWT for compatibility
    jwt_token = create_access_token(user["id"], user["email"], user.get("role", "user"))
    _set_cookies(response, jwt_token, session_token=session_token)
    return {"user": _user_to_public(user), "access_token": jwt_token, "token_type": "bearer"}


async def seed_admin(db):
    """Idempotent admin seeding."""
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@smartcam.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "SmartCam2026!")
    existing = await db.users.find_one({"email": admin_email})
    pw_hash = hash_password(admin_password)
    if existing is None:
        await db.users.insert_one({
            "id": new_id(),
            "email": admin_email,
            "name": "Super Admin",
            "password_hash": pw_hash,
            "role": "super_admin",
            "auth_provider": "password",
            "avatar_url": None,
            "subscription_plan": "enterprise",
            "subscription_status": "active",
            "is_active": True,
            "stripe_customer_id": None,
            "google_drive_connected": False,
            "whatsapp_number": None,
            "created_at": utcnow().isoformat(),
        })
    else:
        # Ensure role is super_admin and password matches env
        updates = {}
        if existing.get("role") != "super_admin":
            updates["role"] = "super_admin"
        if not verify_password(admin_password, existing.get("password_hash", "")):
            updates["password_hash"] = pw_hash
        if updates:
            await db.users.update_one({"email": admin_email}, {"$set": updates})
