from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from collections import defaultdict

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.emissions import EmissionRecord
from app.schemas.emissions import EmissionCreate, EmissionUpdate, EmissionOut

router = APIRouter()

# ─────────────────────────────────────────────
# 🔐 Permission check
# ─────────────────────────────────────────────
def can_register_emissions(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager]

# ─────────────────────────────────────────────
# 🆕 Register new emission record
# ─────────────────────────────────────────────
@router.post("/", response_model=EmissionOut, status_code=201)
async def create_emission_record(
    data: EmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_register_emissions(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    new_record = EmissionRecord(
        **data.dict(),
        user_id=current_user.id
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record

# ─────────────────────────────────────────────
# 📊 List all emissions with optional filters
# ─────────────────────────────────────────────
@router.get("/", response_model=List[EmissionOut])
async def list_emissions(
    vessel_id: Optional[int] = None,
    reporting_period: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(EmissionRecord)

    if vessel_id:
        query = query.where(EmissionRecord.vessel_id == vessel_id)
    if reporting_period:
        query = query.where(EmissionRecord.reporting_period == reporting_period)

    result = await db.execute(query)
    return result.scalars().all()

# ─────────────────────────────────────────────
# 🔍 Get emission detail by ID
# ─────────────────────────────────────────────
@router.get("/{record_id}", response_model=EmissionOut)
async def get_emission_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(EmissionRecord).where(EmissionRecord.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Emission record not found")
    return record

# ─────────────────────────────────────────────
# ✏️ Update emission record
# ─────────────────────────────────────────────
@router.put("/{record_id}", response_model=EmissionOut)
async def update_emission_record(
    record_id: int,
    updates: EmissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_register_emissions(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(EmissionRecord).where(EmissionRecord.id == record_id))
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Emission record not found")

    for key, value in updates.dict(exclude_unset=True).items():
        setattr(record, key, value)

    await db.commit()
    await db.refresh(record)
    return record

# ─────────────────────────────────────────────
# 📈 Aggregated emissions summary per voyage
# ─────────────────────────────────────────────
@router.get("/summary")
async def emissions_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a summary of CO2 emissions per voyage with aggregated metrics.
    Ideal for ESG dashboards.
    """
    result = await db.execute(select(EmissionRecord))
    records = result.scalars().all()

    summary = defaultdict(lambda: {
        "voyage_id": None,
        "vessel": None,
        "co2": 0.0,
        "eexi": 0.0,
        "cii": "C",
        "status": "unknown",
        "count": 0,
    })

    for rec in records:
        key = rec.voyage_id
        s = summary[key]
        s["voyage_id"] = rec.voyage_id
        s["vessel"] = rec.vessel_name
        s["co2"] += rec.co2_emissions_mt
        s["eexi"] += rec.eexi_index or 0
        s["cii"] = rec.cii_rating or "C"
        s["status"] = rec.status or "unknown"
        s["count"] += 1

    return [
        {
            "voyage_id": s["voyage_id"],
            "vessel": s["vessel"],
            "co2": round(s["co2"], 2),
            "eexi": round(s["eexi"] / s["count"], 2) if s["count"] > 0 else 0.0,
            "cii": s["cii"],
            "status": s["status"]
        }
        for s in summary.values()
    ]
