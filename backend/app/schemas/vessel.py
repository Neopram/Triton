from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from datetime import datetime


class VesselType(str, Enum):
    tanker = "Tanker"
    bulker = "Bulker"
    container = "Container"
    lng = "LNG"
    lpg = "LPG"
    ro_ro = "Ro-Ro"
    general_cargo = "General Cargo"


# ───────────────────────────────
# Base schema (shared attributes)
# ───────────────────────────────
class VesselBase(BaseModel):
    name: str = Field(..., example="MT Ocean Spirit")
    imo_number: Optional[str] = Field(None, example="9876543")
    call_sign: Optional[str] = Field(None, example="3FOA9")
    flag: Optional[str] = Field(None, example="Liberia")
    vessel_type: VesselType = Field(..., example="Tanker")
    dwt: Optional[float] = Field(None, example=75000)
    draft: Optional[float] = Field(None, example=11.2)
    loa: Optional[float] = Field(None, example=230.5)
    beam: Optional[float] = Field(None, example=32.2)
    fuel_type: Optional[str] = Field(default="IFO380")
    consumption_at_sea: Optional[float] = Field(default=30.0)
    consumption_at_port: Optional[float] = Field(default=2.5)
    eexi_rating: Optional[str] = Field(None, example="C")
    cii_rating: Optional[str] = Field(None, example="B")
    is_active: Optional[bool] = True


# ───────────────────────────────
# Create schema
# ───────────────────────────────
class VesselCreate(VesselBase):
    pass


# ───────────────────────────────
# Update schema
# ───────────────────────────────
class VesselUpdate(BaseModel):
    name: Optional[str]
    flag: Optional[str]
    vessel_type: Optional[VesselType]
    dwt: Optional[float]
    fuel_type: Optional[str]
    consumption_at_sea: Optional[float]
    consumption_at_port: Optional[float]
    eexi_rating: Optional[str]
    cii_rating: Optional[str]
    is_active: Optional[bool]


# ───────────────────────────────
# Output schema
# ───────────────────────────────
class VesselOut(VesselBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
