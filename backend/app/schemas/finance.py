from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 📥 Shared base schema
# ─────────────────────────────────────────────
class FinanceBase(BaseModel):
    voyage_id: int
    revenue_usd: float = Field(..., example=100000)
    cost_bunkers_usd: Optional[float] = Field(default=0.0, example=40000)
    cost_ports_usd: Optional[float] = Field(default=0.0, example=15000)
    cost_canals_usd: Optional[float] = Field(default=0.0, example=5000)
    other_costs_usd: Optional[float] = Field(default=0.0, example=2000)
    comment: Optional[str] = Field(None, example="Corrected bunker estimate after discharge")


# ─────────────────────────────────────────────
# 🆕 Create schema
# ─────────────────────────────────────────────
class FinanceCreate(FinanceBase):
    pass


# ─────────────────────────────────────────────
# 🔁 Update schema
# ─────────────────────────────────────────────
class FinanceUpdate(BaseModel):
    revenue_usd: Optional[float]
    cost_bunkers_usd: Optional[float]
    cost_ports_usd: Optional[float]
    cost_canals_usd: Optional[float]
    other_costs_usd: Optional[float]
    comment: Optional[str]


# ─────────────────────────────────────────────
# 📤 Response schema
# ─────────────────────────────────────────────
class FinanceOut(FinanceBase):
    id: int
    user_id: int
    total_costs_usd: float
    profit_usd: float
    pnl_margin_pct: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True
