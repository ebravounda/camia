"""Pydantic models for SmartCam SaaS."""
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# ===== USER =====
class UserBase(BaseModel):
    email: EmailStr
    name: str


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(UserBase):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: Literal["user", "super_admin"] = "user"
    auth_provider: Literal["password", "google"] = "password"
    avatar_url: Optional[str] = None
    subscription_plan: Literal["free", "pro", "enterprise"] = "free"
    subscription_status: Literal["inactive", "active", "past_due", "canceled"] = "inactive"
    is_active: bool = True
    created_at: datetime


class UserDoc(UserPublic):
    password_hash: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    google_drive_connected: bool = False
    whatsapp_number: Optional[str] = None


# ===== DEVICE (Raspberry Pi) =====
class DeviceBase(BaseModel):
    name: str
    location: Optional[str] = None


class DeviceCreate(DeviceBase):
    pass


class Device(DeviceBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    user_id: str
    pairing_token: str
    is_paired: bool = False
    status: Literal["offline", "online", "warning"] = "offline"
    last_seen: Optional[datetime] = None
    cpu_temp: Optional[float] = None
    cpu_usage: Optional[float] = None
    ip_address: Optional[str] = None
    agent_version: Optional[str] = None
    hostname: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


# ===== CAMERA =====
class CameraBase(BaseModel):
    name: str
    device_id: str
    usb_index: int = 0
    enabled: bool = True


class CameraCreate(CameraBase):
    pass


class Camera(CameraBase):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    user_id: str
    status: Literal["offline", "live", "error"] = "offline"
    last_event_at: Optional[datetime] = None
    last_thumbnail: Optional[str] = None  # base64 JPEG, small
    last_thumbnail_at: Optional[datetime] = None
    detection_zones: List[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# ===== EVENT =====
class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    user_id: str
    device_id: str
    camera_id: str
    camera_name: Optional[str] = None
    event_type: Literal["person", "unknown_face", "animal", "vehicle", "motion", "suspicious"] = "motion"
    severity: Literal["low", "medium", "high"] = "low"
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    clip_url: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


# ===== PLAN =====
class Plan(BaseModel):
    id: str
    name: str
    price_monthly: float
    currency: str = "usd"
    features: List[str]
    max_cameras: int
    max_devices: int
    storage_days: int


# ===== PAYMENT TRANSACTION =====
class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=new_id)
    user_id: str
    session_id: str
    amount: float
    currency: str
    plan_id: str
    payment_status: Literal["initiated", "pending", "paid", "failed", "expired"] = "initiated"
    status: str = "open"
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ===== AUTH RESPONSES =====
class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
