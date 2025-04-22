from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.models.vessel import Vessel
from app.schemas.vessel import VesselCreate, VesselOut, VesselUpdate
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.services.ais_simulator import get_fake_ais_data

router = APIRouter()


# ─────────────────────────────────────────────
# 🔐 Helper: check if user can edit vessels
# ─────────────────────────────────────────────
def can_manage_vessels(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager]


# ─────────────────────────────────────────────
# 📥 Register new vessel
# ─────────────────────────────────────────────
@router.post("/", response_model=VesselOut, status_code=201)
async def create_vessel(
    vessel: VesselCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_vessels(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    new_vessel = Vessel(**vessel.dict())
    db.add(new_vessel)
    await db.commit()
    await db.refresh(new_vessel)
    return new_vessel


# ─────────────────────────────────────────────
# 📃 List all active vessels
# ─────────────────────────────────────────────
@router.get("/", response_model=List[VesselOut])
async def list_vessels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Vessel).where(Vessel.is_active == True))
    return result.scalars().all()


# ─────────────────────────────────────────────
# 🔍 Get vessel by ID
# ─────────────────────────────────────────────
@router.get("/{vessel_id}", response_model=VesselOut)
async def get_vessel(
    vessel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Vessel).where(Vessel.id == vessel_id))
    vessel = result.scalar_one_or_none()

    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


# ─────────────────────────────────────────────
# 📝 Update vessel
# ─────────────────────────────────────────────
@router.put("/{vessel_id}", response_model=VesselOut)
async def update_vessel(
    vessel_id: int,
    updates: VesselUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_vessels(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(Vessel).where(Vessel.id == vessel_id))
    vessel = result.scalar_one_or_none()
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")

    for key, value in updates.dict(exclude_unset=True).items():
        setattr(vessel, key, value)

    await db.commit()
    await db.refresh(vessel)
    return vessel


# ─────────────────────────────────────────────
# ❌ Delete vessel (soft delete)
# ─────────────────────────────────────────────
@router.delete("/{vessel_id}", status_code=204)
async def delete_vessel(
    vessel_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_vessels(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(Vessel).where(Vessel.id == vessel_id))
    vessel = result.scalar_one_or_none()
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")

    vessel.is_active = False
    await db.commit()


# ─────────────────────────────────────────────
# 🌍 AIS Tracking Simulation Endpoint
# ─────────────────────────────────────────────
@router.get("/tracking", tags=["Vessels"])
async def get_vessel_tracking(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns simulated AIS data for vessels, including position, ETA, speed, and status.
    """
    try:
        ais_data = get_fake_ais_data()
        return ais_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate AIS data: {str(e)}")
