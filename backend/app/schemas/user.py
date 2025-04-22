from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class UserRole(str, Enum):
    admin = "admin"
    fleet_manager = "fleet_manager"
    operator = "operator"
    viewer = "viewer"


# ---------- SHARED ----------

class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.viewer
    is_active: bool = True


# ---------- CREATE ----------

class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


# ---------- UPDATE ----------

class UserUpdate(BaseModel):
    full_name: Optional[str]
    password: Optional[str]
    role: Optional[UserRole]
    is_active: Optional[bool]


# ---------- RESPONSE ----------

class UserOut(UserBase):
    id: int
    is_superuser: bool = False
    created_at: datetime

    class Config:
        orm_mode = True


# ---------- AUTH ----------

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str  # user_id
    exp: int
