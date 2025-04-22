from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─────────────────────────────────────────────
# 📥 Base Insight Schema 
# ─────────────────────────────────────────────
class MarketInsightBase(BaseModel):
    insights: str = Field(..., example="The Baltic Dry Index has increased by 15% in the last week...")
    engine_used: Optional[str] = Field(default="phi3", example="deepseek")


# ─────────────────────────────────────────────
# 📤 Simple Response Schema
# ─────────────────────────────────────────────
class MarketInsight(BaseModel):
    insights: str


# ─────────────────────────────────────────────
# 📊 Feedback Request Schema
# ─────────────────────────────────────────────
class InsightFeedback(BaseModel):
    rating: float = Field(..., ge=1, le=5, example=4.5)
    feedback: Optional[str] = Field(None, example="Very useful analysis of the current market trends.")


# ─────────────────────────────────────────────
# 📤 Complete Output Schema
# ─────────────────────────────────────────────
class MarketInsightOut(MarketInsightBase):
    id: int
    user_id: int
    created_at: datetime
    rating: Optional[float] = None
    feedback: Optional[str] = None

    class Config:
        orm_mode = True

# ─────────────────────────────────────────────
# 📤 Output Schema
# ─────────────────────────────────────────────
class MarketInsightOut(BaseModel):
    id: int
    insights: str
    engine_used: Optional[str] = None
    created_at: datetime
    user_id: int
    rating: Optional[float] = None
    feedback: Optional[str] = None

    class Config:
        orm_mode = True