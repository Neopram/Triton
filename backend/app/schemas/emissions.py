from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 📥 Shared Base Schema
# ─────────────────────────────────────────────
class EmissionBase(BaseModel):
    vessel_id: int
    voyage_id: Optional[int] = None

    reporting_period: str = Field(..., example="2024-Q2")
    fuel_type: str = Field(..., example="VLSFO")
    fuel_consumed_mt: float = Field(..., example=105.0)
    co2_emitted_mt: float = Field(..., example=315.0)  # Based on emission factor

    eexi_rating: Optional[str] = Field(None, example="C")
    cii_score: Optional[float] = Field(None, example=11.2)
    cii_rating: Optional[str] = Field(None, example="B")
    regulation_flag: Optional[str] = Field(default="EU ETS")


# ─────────────────────────────────────────────
# ✅ Create Schema
# ─────────────────────────────────────────────
class EmissionCreate(EmissionBase):
    pass


# ─────────────────────────────────────────────
# ✏️ Update Schema
# ─────────────────────────────────────────────
class EmissionUpdate(BaseModel):
    fuel_consumed_mt: Optional[float]
    co2_emitted_mt: Optional[float]
    eexi_rating: Optional[str]
    cii_score: Optional[float]
    cii_rating: Optional[str]
    regulation_flag: Optional[str]


# ─────────────────────────────────────────────
# 📤 Response Schema
# ─────────────────────────────────────────────
class EmissionOut(EmissionBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        orm_mode = True
