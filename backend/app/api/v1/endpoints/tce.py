from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()

class TCERequest(BaseModel):
    voyage_days: float = Field(..., gt=0)
    distance_nm: float = Field(..., gt=0)
    daily_consumption_mt: float = Field(..., gt=0)
    bunker_price_usd_per_mt: float = Field(..., gt=0)
    freight_rate_usd: float = Field(..., gt=0)
    cargo_quantity_mt: float = Field(..., gt=0)
    cargo_type: Literal["clean", "dirty", "dry"] = "clean"
    port_fees_usd: float = 30000
    canal_fees_usd: float = 20000
    other_costs_usd: float = 10000

class TCEResponse(BaseModel):
    tce_usd_per_day: float
    total_bunker_cost: float
    total_costs: float
    gross_revenue: float
    net_profit: float
    pnl_margin_pct: float
    voyage_days: float

@router.post("/calculate", response_model=TCEResponse)
async def calculate_tce(
    request: TCERequest,
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "fleet_manager", "operator"]:
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    bunker_cost = request.daily_consumption_mt * request.voyage_days * request.bunker_price_usd_per_mt
    gross_revenue = request.freight_rate_usd * request.cargo_quantity_mt / 1000  # freight per 1000 MT
    total_costs = bunker_cost + request.port_fees_usd + request.canal_fees_usd + request.other_costs_usd
    net_profit = gross_revenue - total_costs
    tce = net_profit / request.voyage_days
    margin = round((net_profit / gross_revenue) * 100, 2) if gross_revenue > 0 else 0

    return TCEResponse(
        tce_usd_per_day=round(tce, 2),
        total_bunker_cost=round(bunker_cost, 2),
        total_costs=round(total_costs, 2),
        gross_revenue=round(gross_revenue, 2),
        net_profit=round(net_profit, 2),
        pnl_margin_pct=margin,
        voyage_days=request.voyage_days
    )
