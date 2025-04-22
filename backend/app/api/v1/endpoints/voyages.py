from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.models.voyage import Voyage, VoyageStatus
from app.schemas.voyage import VoyageCreate, VoyageOut, VoyageUpdate
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole

router = APIRouter()


def can_manage_voyages(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager, UserRole.operator]


# ─────────────────────────────────────────────
# 🧾 Create Voyage
# ─────────────────────────────────────────────
@router.post("/", response_model=VoyageOut, status_code=201)
async def create_voyage(
    data: VoyageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not can_manage_voyages(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    new_voyage = Voyage(**data.dict(), user_id=current_user.id)
    db.add(new_voyage)
    await db.commit()
    await db.refresh(new_voyage)
    return new_voyage


# ─────────────────────────────────────────────
# 📃 List Voyages (all active)
# ─────────────────────────────────────────────
@router.get("/", response_model=List[VoyageOut])
async def list_voyages(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Voyage).where(Voyage.status != VoyageStatus.cancelled)
    result = await db.execute(query)
    return result.scalars().all()


# ─────────────────────────────────────────────
# 🔍 Get Voyage by ID
# ─────────────────────────────────────────────
@router.get("/{voyage_id}", response_model=VoyageOut)
async def get_voyage(
    voyage_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Voyage).where(Voyage.id == voyage_id))
    voyage = result.scalar_one_or_none()
    if not voyage:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return voyage


# ─────────────────────────────────────────────
# ✏️ Update Voyage
# ─────────────────────────────────────────────
@router.put("/{voyage_id}", response_model=VoyageOut)
async def update_voyage(
    voyage_id: int,
    updates: VoyageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not can_manage_voyages(current_user):
        raise HTTPException(status_code=403, detail="Insufficient privileges")

    result = await db.execute(select(Voyage).where(Voyage.id == voyage_id))
    voyage = result.scalar_one_or_none()
    if not voyage:
        raise HTTPException(status_code=404, detail="Voyage not found")

    for key, value in updates.dict(exclude_unset=True).items():
        setattr(voyage, key, value)

    await db.commit()
    await db.refresh(voyage)
    return voyage
