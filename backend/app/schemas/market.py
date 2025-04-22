from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 📥 Base Shared Schema
# ─────────────────────────────────────────────
class MarketBase(BaseModel):
    vessel_type: str = Field(..., example="Aframax")
    cargo_type: Optional[str] = Field(None, example="Diesel")
    route: str = Field(..., example="USG → NWE")
    rate_type: Optional[str] = Field(default="Spot", example="Contract")
    rate_usd_per_mt: float = Field(..., example=25.5)
    source: Optional[str] = Field(default="Manual Entry")
    report_date: datetime = Field(..., example="2024-04-17T12:00:00Z")
    comment: Optional[str] = Field(None, example="From Clarkson Report 2024-W15")


# ─────────────────────────────────────────────
# 🆕 Create Schema
# ─────────────────────────────────────────────
class MarketCreate(MarketBase):
    pass


# ─────────────────────────────────────────────
# ✏️ Update Schema
# ─────────────────────────────────────────────
class MarketUpdate(BaseModel):
    rate_usd_per_mt: Optional[float]
    rate_type: Optional[str]
    source: Optional[str]
    comment: Optional[str]


# ─────────────────────────────────────────────
# 📤 Output Schema
# ─────────────────────────────────────────────
class MarketOut(MarketBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True


# ─────────────────────────────────────────────
# 🧠 AI Market Insight Schema (NEW)
# ─────────────────────────────────────────────
class MarketInsight(BaseModel):
    insights: str
