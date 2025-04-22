from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime
import time
import uuid
import os

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.market import MarketReport
from app.models.market_insight import MarketInsightRecord
from app.schemas.market import MarketCreate, MarketUpdate, MarketOut
from app.schemas.market_insight import MarketInsight, MarketInsightOut, InsightFeedback
from app.services.ai_engine import query_ai_engine
from app.middleware.permissions import verify_permission, ResourceType, Operation
from app.dependencies.redis_cache import get_market_cache, get_insight_cache
from app.core.logging import api_logger, log_api_request, log_ai_request

router = APIRouter()

# Helper function to check market data permissions
def can_add_market_data(user: User) -> bool:
    return user.role in [UserRole.admin, UserRole.fleet_manager, UserRole.analyst]

# ─────────────────────────────────────────────
# 📈 Register new market rate
# ─────────────────────────────────────────────
@router.post("/", response_model=MarketOut, status_code=201)
async def create_market_report(
    data: MarketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.MARKET, Operation.CREATE)),
    market_cache = Depends(get_market_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        report = MarketReport(
            **data.dict(),
            user_id=current_user.id
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        
        # Invalidate cache
        await market_cache.delete("latest_reports")
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/market", 201, processing_time, current_user.id
        )
        
        return report
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/market", 500, processing_time, current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 📊 List market rates with optional filters
# ─────────────────────────────────────────────
@router.get("/", response_model=List[MarketOut])
async def list_market_reports(
    route: Optional[str] = None,
    vessel_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.MARKET, Operation.LIST)),
    market_cache = Depends(get_market_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Create cache key based on parameters
    cache_params = f"{route}:{vessel_type}:{start_date}:{end_date}:{limit}:{offset}"
    cache_key = f"reports:{cache_params}"
    
    try:
        # Try to get from cache first
        cached_data = await market_cache.get(cache_key)
        if cached_data:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", "/market", 200, processing_time, current_user.id
            )
            return cached_data
        
        # If not in cache, query the database
        query = select(MarketReport)

        if route:
            query = query.where(MarketReport.route == route)
        if vessel_type:
            query = query.where(MarketReport.vessel_type == vessel_type)
        if start_date:
            query = query.where(MarketReport.report_date >= start_date)
        if end_date:
            query = query.where(MarketReport.report_date <= end_date)

        query = query.order_by(desc(MarketReport.report_date))
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        reports = result.scalars().all()
        
        # Convert to dictionaries for caching
        reports_data = [report.__dict__ for report in reports]
        for report_data in reports_data:
            # Remove SQLAlchemy instance state
            if '_sa_instance_state' in report_data:
                report_data.pop('_sa_instance_state')
        
        # Cache for 5 minutes
        await market_cache.set(cache_key, reports_data, expire=300)
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market", 200, processing_time, current_user.id
        )
        
        return reports
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market", 500, processing_time, current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 🧠 AI Insight from market upload (PDF/CSV/text)
# ─────────────────────────────────────────────
@router.post("/analyze", response_model=MarketInsight)
async def analyze_market_text(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.CREATE)),
    insight_cache = Depends(get_insight_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        text = (await file.read()).decode("utf-8")
        prompt = f"Summarize this shipping market report:\n\n{text}"
        
        # Use the centralized engine
        insight_result = await query_ai_engine(prompt=prompt)
        
        # Handle both string and dictionary responses from the AI engine
        if isinstance(insight_result, dict) and 'response' in insight_result:
            insight = insight_result['response']
        elif isinstance(insight_result, str):
            insight = insight_result
        else:
            insight = str(insight_result)
        
        # Calculate tokens (approximate)
        tokens = len(text.split()) + len(insight.split())
        
        # Log AI request
        ai_processing_time = time.time() - start_time
        log_ai_request(
            engine=os.getenv("AI_ENGINE", "phi3"),
            prompt_type="market_analysis",
            tokens=tokens,
            processing_time=ai_processing_time,
            user_id=current_user.id
        )

        record = MarketInsightRecord(
            user_id=current_user.id,
            content=text,
            insights=insight[:1500],
            engine_used=os.getenv("AI_ENGINE", "phi3"),
            prompt=prompt,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        
        # Invalidate insights cache
        await insight_cache.delete(f"user:{current_user.id}:latest_insight")
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/market/analyze", 200, processing_time, current_user.id
        )

        return {"insights": insight[:800]}
    except HTTPException as he:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/market/analyze", he.status_code, processing_time, 
            current_user.id, he.detail
        )
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", "/market/analyze", 500, processing_time, current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# ─────────────────────────────────────────────
# 📤 Fetch latest market insight
# ─────────────────────────────────────────────
@router.get("/latest-insight", response_model=MarketInsightOut)
async def get_latest_market_insight(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.READ)),
    insight_cache = Depends(get_insight_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    cache_key = f"user:{current_user.id}:latest_insight"
    
    try:
        # Try to get from cache first
        cached_data = await insight_cache.get(cache_key)
        if cached_data:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", "/market/latest-insight", 200, processing_time, current_user.id
            )
            return cached_data
        
        # If not in cache, query the database
        stmt = select(MarketInsightRecord).where(
            MarketInsightRecord.user_id == current_user.id
        ).order_by(desc(MarketInsightRecord.created_at)).limit(1)

        result = await db.execute(stmt)
        latest = result.scalar_one_or_none()

        if not latest:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", "/market/latest-insight", 404, processing_time, 
                current_user.id, "No market insights found"
            )
            raise HTTPException(status_code=404, detail="No market insights found")
        
        # Convert to dict for caching
        latest_data = {k: v for k, v in latest.__dict__.items() if not k.startswith('_')}
        
        # Cache for 10 minutes
        await insight_cache.set(cache_key, latest_data, expire=600)
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/latest-insight", 200, processing_time, current_user.id
        )
        
        return latest
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/latest-insight", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 📋 List all insights for a user
# ─────────────────────────────────────────────
@router.get("/insights", response_model=List[MarketInsightOut])
async def list_user_insights(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.LIST)),
    insight_cache = Depends(get_insight_cache),
    limit: int = Query(10, ge=1, le=100)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    cache_key = f"user:{current_user.id}:insights:{limit}"
    
    try:
        # Try to get from cache first
        cached_data = await insight_cache.get(cache_key)
        if cached_data:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", "/market/insights", 200, processing_time, current_user.id
            )
            return cached_data
        
        stmt = select(MarketInsightRecord).where(
            MarketInsightRecord.user_id == current_user.id
        ).order_by(desc(MarketInsightRecord.created_at)).limit(limit)

        result = await db.execute(stmt)
        insights = result.scalars().all()
        
        # Convert to dicts for caching
        insights_data = []
        for insight in insights:
            insight_dict = {k: v for k, v in insight.__dict__.items() if not k.startswith('_')}
            insights_data.append(insight_dict)
        
        # Cache for 5 minutes
        await insight_cache.set(cache_key, insights_data, expire=300)
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/insights", 200, processing_time, current_user.id
        )
        
        return insights
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/insights", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 🔍 Get insight by ID
# ─────────────────────────────────────────────
@router.get("/insights/{insight_id}", response_model=MarketInsightOut)
async def get_insight_by_id(
    insight_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.READ)),
    insight_cache = Depends(get_insight_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    cache_key = f"insight:{insight_id}"
    
    try:
        # Try to get from cache first
        cached_data = await insight_cache.get(cache_key)
        if cached_data:
            # Verify the user has access to this insight
            if cached_data.get("user_id") != current_user.id and current_user.role != UserRole.admin:
                processing_time = time.time() - start_time
                log_api_request(
                    request_id, "GET", f"/market/insights/{insight_id}", 403, processing_time, 
                    current_user.id, "Not authorized to access this insight"
                )
                raise HTTPException(status_code=403, detail="Not authorized to access this insight")
            
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", f"/market/insights/{insight_id}", 200, processing_time, current_user.id
            )
            return cached_data
        
        stmt = select(MarketInsightRecord).where(
            MarketInsightRecord.id == insight_id
        )
        
        if current_user.role != UserRole.admin:
            # Non-admins can only see their own insights
            stmt = stmt.where(MarketInsightRecord.user_id == current_user.id)
        
        result = await db.execute(stmt)
        insight = result.scalar_one_or_none()
        
        if not insight:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", f"/market/insights/{insight_id}", 404, processing_time,
                current_user.id, "Market insight not found"
            )
            raise HTTPException(status_code=404, detail="Market insight not found")
        
        # Convert to dict for caching
        insight_data = {k: v for k, v in insight.__dict__.items() if not k.startswith('_')}
        
        # Cache for 1 hour
        await insight_cache.set(cache_key, insight_data, expire=3600)
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", f"/market/insights/{insight_id}", 200, processing_time, current_user.id
        )
        
        return insight
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", f"/market/insights/{insight_id}", 500, processing_time, 
            current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 📝 Submit feedback for an insight
# ─────────────────────────────────────────────
@router.post("/insights/{insight_id}/feedback", status_code=200)
async def add_insight_feedback(
    insight_id: int,
    feedback: InsightFeedback,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.UPDATE)),
    insight_cache = Depends(get_insight_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    try:
        # Find the insight
        stmt = select(MarketInsightRecord).where(
            MarketInsightRecord.id == insight_id
        )
        
        # Users can only update their own insights unless they're admins
        if current_user.role != UserRole.admin:
            stmt = stmt.where(MarketInsightRecord.user_id == current_user.id)
        
        result = await db.execute(stmt)
        insight = result.scalar_one_or_none()
        
        if not insight:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "POST", f"/market/insights/{insight_id}/feedback", 404, 
                processing_time, current_user.id, "Market insight not found"
            )
            raise HTTPException(status_code=404, detail="Market insight not found")
        
        # Update the feedback
        insight.rating = feedback.rating
        insight.feedback = feedback.feedback
        
        await db.commit()
        
        # Invalidate cache
        await insight_cache.delete(f"insight:{insight_id}")
        await insight_cache.delete(f"user:{current_user.id}:insights:*")
        await insight_cache.delete(f"user:{current_user.id}:insight_stats")
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", f"/market/insights/{insight_id}/feedback", 200, 
            processing_time, current_user.id
        )
        
        return {"status": "success"}
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "POST", f"/market/insights/{insight_id}/feedback", 500, 
            processing_time, current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# 📊 Get insights statistics
# ─────────────────────────────────────────────
@router.get("/insights/stats")
async def get_insight_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(verify_permission(ResourceType.INSIGHT, Operation.READ)),
    insight_cache = Depends(get_insight_cache)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    cache_key = f"user:{current_user.id}:insight_stats"
    
    try:
        # Try to get from cache first
        cached_data = await insight_cache.get(cache_key)
        if cached_data:
            processing_time = time.time() - start_time
            log_api_request(
                request_id, "GET", "/market/insights/stats", 200, processing_time, current_user.id
            )
            return cached_data
        
        # Get total count of insights
        count_stmt = select(func.count(MarketInsightRecord.id)).where(
            MarketInsightRecord.user_id == current_user.id
        )
        total_count = await db.execute(count_stmt)
        total_count = total_count.scalar_one()
        
        # Get count of rated insights
        rated_stmt = select(func.count(MarketInsightRecord.id)).where(
            MarketInsightRecord.user_id == current_user.id,
            MarketInsightRecord.rating.isnot(None)
        )
        rated_count = await db.execute(rated_stmt)
        rated_count = rated_count.scalar_one()
        
        # Get average rating of insights with ratings
        rating_stmt = select(func.avg(MarketInsightRecord.rating)).where(
            MarketInsightRecord.user_id == current_user.id,
            MarketInsightRecord.rating.isnot(None)
        )
        avg_rating = await db.execute(rating_stmt)
        avg_rating = avg_rating.scalar_one()
        
        # Get count by engine
        engine_counts = {}
        for engine in ["phi3", "deepseek"]:
            engine_stmt = select(func.count(MarketInsightRecord.id)).where(
                MarketInsightRecord.user_id == current_user.id,
                MarketInsightRecord.engine_used == engine
            )
            count = await db.execute(engine_stmt)
            engine_counts[engine] = count.scalar_one()
        
        # Build stats object
        stats = {
            "total_count": total_count,
            "rated_count": rated_count,
            "average_rating": float(avg_rating) if avg_rating else None,
            "engine_counts": engine_counts
        }
        
        # Cache for 5 minutes
        await insight_cache.set(cache_key, stats, expire=300)
        
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/insights/stats", 200, processing_time, current_user.id
        )
        
        return stats
    except Exception as e:
        processing_time = time.time() - start_time
        log_api_request(
            request_id, "GET", "/market/insights/stats", 500, 
            processing_time, current_user.id, str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))