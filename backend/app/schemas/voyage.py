from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class VoyageStatus(str, Enum):
    planned = "Planned"
    ongoing = "Ongoing"
    completed = "Completed"
    cancelled = "Cancelled"


# ─────────────────────────────────────────────
# 🧩 Shared Base Model
# ─────────────────────────────────────────────
class VoyageBase(BaseModel):
    vessel_id: int
    cargo_type: Optional[str] = Field(None, example="Crude Oil")
    cargo_quantity: Optional[float] = Field(None, example=80000)

    origin_port: str = Field(..., example="Houston")
    destination_port: str = Field(..., example="Rotterdam")

    laycan_start: Optional[datetime]
    laycan_end: Optional[datetime]
    departure_date: Optional[datetime]
    arrival_date: Optional[datetime]

    freight_rate: Optional[float] = Field(None, example=15.5)  # USD/MT
    bunkers_cost: Optional[float] = Field(None, example=45000)
    port_charges: Optional[float] = Field(None, example=12000)
    canal_fees: Optional[float] = Field(None, example=30000)
    tce_result: Optional[float] = Field(None, example=19500)

    status: Optional[VoyageStatus] = VoyageStatus.planned


# ─────────────────────────────────────────────
# ✍️ Create Model
# ─────────────────────────────────────────────
class VoyageCreate(VoyageBase):
    pass


# ─────────────────────────────────────────────
# ✏️ Update Model
# ─────────────────────────────────────────────
class VoyageUpdate(BaseModel):
    cargo_type: Optional[str]
    cargo_quantity: Optional[float]
    destination_port: Optional[str]
    arrival_date: Optional[datetime]
    freight_rate: Optional[float]
    bunkers_cost: Optional[float]
    port_charges: Optional[float]
    canal_fees: Optional[float]
    status: Optional[VoyageStatus]
    tce_result: Optional[float]


# ─────────────────────────────────────────────
# 📤 Response Model
# ─────────────────────────────────────────────
class VoyageOut(VoyageBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
        
        
        
