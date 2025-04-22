from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.deepseek_engine import query_deepseek
from app.services.phi3_engine import query_phi3

router = APIRouter()


class AIQuery(BaseModel):
    prompt: str
    mode: str = "auto"  # "deepseek", "phi3", or "auto"


class AIResponse(BaseModel):
    engine_used: str
    result: str


# ─────────────────────────────────────────────
# 🧠 Unified AI interface
# ─────────────────────────────────────────────
@router.post("/ask", response_model=AIResponse)
async def ask_ai(
    query: AIQuery,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if query.mode == "deepseek":
        try:
            result = await query_deepseek(query.prompt)
            return AIResponse(engine_used="deepseek", result=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DeepSeek failed: {str(e)}")

    elif query.mode == "phi3":
        try:
            result = query_phi3(query.prompt)
            return AIResponse(engine_used="phi3", result=result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Phi-3 failed: {str(e)}")

    elif query.mode == "auto":
        try:
            # First try DeepSeek
            result = await query_deepseek(query.prompt)
            return AIResponse(engine_used="deepseek", result=result)
        except:
            try:
                # Fallback to Phi-3 if offline
                result = query_phi3(query.prompt)
                return AIResponse(engine_used="phi3", result=result)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"No engine available: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Invalid mode: choose 'deepseek', 'phi3', or 'auto'")
