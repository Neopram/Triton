from fastapi import APIRouter, Depends, HTTPException, Body, status
from typing import Dict, Any, List
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_current_user
from app.middleware.permissions import admin_only
from app.services.ai_engine import get_available_engines, get_current_ai_engine
from app.models.user import User

router = APIRouter()

class AIEngineConfig(BaseModel):
    engine: str

class AIEngineInfo(BaseModel):
    current_engine: str
    available_engines: List[str]
    is_valid: bool

# ─────────────────────────────────────────────
# 🔍 Get current AI engine configuration
# ─────────────────────────────────────────────
@router.get("/ai-engine", response_model=AIEngineInfo)
async def get_ai_engine_config(
    current_user: User = Depends(get_current_user)
):
    """Get the current AI engine configuration."""
    return await get_current_ai_engine()

# ─────────────────────────────────────────────
# ✏️ Update AI engine configuration (admin only)
# ─────────────────────────────────────────────
@router.post("/ai-engine", response_model=AIEngineInfo)
async def update_ai_engine_config(
    config: AIEngineConfig,
    current_user: User = Depends(admin_only)
):
    """Update the AI engine configuration (admin only)."""
    available_engines = get_available_engines()
    
    if config.engine not in available_engines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid engine. Available options: {', '.join(available_engines)}"
        )
    
    # In a real-world scenario, you would update a database setting here
    # For now, we'll simulate a config update that lasts until server restart
    settings.AI_ENGINE = config.engine
    
    return {
        "current_engine": config.engine,
        "available_engines": available_engines,
        "is_valid": True
    }