from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.models.finance import FinanceRecord
from app.models.user import User, UserRole
from app.schemas.finance import FinanceCreate, FinanceUpdate, FinanceOut
from app.core.database import get_db
from app.core.security import get_current_user

router = APIRouter()


def can_edit_finance(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager]


# ─────────────────────────────────────────────
# 💰 Register PnL entry for a voyage
# ─────────────────────────────────────────────
@router.post("/", response_model=FinanceOut, status_code=201)
async def create_finance_record(
    data: FinanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_edit_finance(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    total_costs = (
        (data.cost_bunkers_usd or 0) +
        (data.cost_ports_usd or 0) +
        (data.cost_canals_usd or 0) +
        (data.other_costs_usd or 0)
    )
    profit = data.revenue_usd - total_costs
    margin = round((profit / data.revenue_usd) * 100, 2) if data.revenue_usd else 0.0

    new_record = FinanceRecord(
        voyage_id=data.voyage_id,
        user_id=current_user.id,
        revenue_usd=data.revenue_usd,
        cost_bunkers_usd=data.cost_bunkers_usd,
        cost_ports_usd=data.cost_ports_usd,
        cost_canals_usd=data.cost_canals_usd,
        other_costs_usd=data.other_costs_usd,
        total_costs_usd=total_costs,
        profit_usd=profit,
        pnl_margin_pct=margin,
        comment=data.comment
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record


# ─────────────────────────────────────────────
# 📃 List all finance records (admin only)
# ─────────────────────────────────────────────
@router.get("/", response_model=List[FinanceOut])
async def list_finance_records(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.admin, UserRole.fleet_manager]:
        raise HTTPException(status_code=403, detail="Only fleet managers and admins can view full finance data")

    result = await db.execute(select(FinanceRecord))
    return result.scalars().all()


# ─────────────────────────────────────────────
# 🔎 Get single record
# ─────────────────────────────────────────────
@router.get("/{record_id}", response_model=FinanceOut)
async def get_finance_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(FinanceRecord).where(FinanceRecord.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Finance record not found")
    return record


# ─────────────────────────────────────────────
# ✏️ Update record
# ─────────────────────────────────────────────
@router.put("/{record_id}", response_model=FinanceOut)
async def update_finance_record(
    record_id: int,
    updates: FinanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_edit_finance(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(FinanceRecord).where(FinanceRecord.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Finance record not found")

    # Apply changes
    for key, value in updates.dict(exclude_unset=True).items():
        setattr(record, key, value)

    # Recalculate totals
    record.total_costs_usd = sum([
        record.cost_bunkers_usd or 0,
        record.cost_ports_usd or 0,
        record.cost_canals_usd or 0,
        record.other_costs_usd or 0,
    ])
    record.profit_usd = record.revenue_usd - record.total_costs_usd
    record.pnl_margin_pct = round((record.profit_usd / record.revenue_usd) * 100, 2) if record.revenue_usd else 0.0

    await db.commit()
    await db.refresh(record)
    return record

# ─────────────────────────────────────────────
# 📊 Dashboard Summary Endpoint
# ─────────────────────────────────────────────
@router.get("/dashboard-summary")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.admin, UserRole.fleet_manager, UserRole.operator]:
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch all records (in real system: optimize with cache or preaggregation)
    result = await db.execute(select(FinanceRecord))
    records = result.scalars().all()

    if not records:
        return {
            "vessels_active": 0,
            "avg_tce": 0,
            "co2_emissions": 0,
            "routes_active": 0,
            "monthly_pnl": []
        }

    # Simulate extracted KPIs (you can replace this with real joins later)
    vessels_active = len(set([r.voyage_id for r in records]))
    avg_tce = sum([r.profit_usd for r in records]) // len(records)
    co2_emissions = round(sum([r.total_costs_usd for r in records]) * 0.0005, 2)  # Dummy logic
    routes_active = min(len(records), 9)

    # Monthly PnL simulation (you could later join with actual voyage date)
    monthly_pnl = [
        {"month": "Jan", "pnl": 210000},
        {"month": "Feb", "pnl": 185000},
        {"month": "Mar", "pnl": 198500},
        {"month": "Apr", "pnl": 175400},
        {"month": "May", "pnl": 221000},
        {"month": "Jun", "pnl": 240000},
    ]

    return {
        "vessels_active": vessels_active,
        "avg_tce": avg_tce,
        "co2_emissions": co2_emissions,
        "routes_active": routes_active,
        "monthly_pnl": monthly_pnl
    }

