# Path: backend/app/services/pnl.py

import time
import json
import uuid
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.sql.expression import cast
from sqlalchemy.types import Float, Integer

from app.models.user import User, UserRole
from app.models.finance import PnLRecord, PnLForecast, PnLBenchmark
from app.models.voyage import Voyage
from app.models.vessel import Vessel
from app.schemas.finance import PnLInput, PnLReport, PnLTarget, PnLAnalysis
from app.core.logging import api_logger
from app.dependencies.redis_cache import get_finance_cache
from app.services.ai_engine import query_ai_engine

# Industry benchmarks for profitability by vessel type (%)
PROFITABILITY_BENCHMARKS = {
    "BULK_CARRIER": 12.5,
    "TANKER": 15.0,
    "CONTAINER": 16.5,
    "GENERAL_CARGO": 10.0,
    "REFRIGERATED": 14.0,
    "RO_RO": 11.5,
    "LNG_CARRIER": 18.0,
    "CRUISE": 22.0
}

# Cost component reference percentages (typical industry distribution)
COST_DISTRIBUTION_REFERENCE = {
    "BULK_CARRIER": {
        "fuel_cost": 45.0,
        "port_fees": 15.0,
        "crew_cost": 20.0,
        "maintenance": 10.0,
        "other": 10.0
    },
    "TANKER": {
        "fuel_cost": 40.0,
        "port_fees": 12.0,
        "crew_cost": 18.0,
        "maintenance": 15.0,
        "other": 15.0
    },
    "CONTAINER": {
        "fuel_cost": 50.0,
        "port_fees": 18.0,
        "crew_cost": 15.0,
        "maintenance": 10.0,
        "other": 7.0
    }
    # Additional vessel types can be added here
}

class PnLCalculator:
    """
    Advanced financial performance calculator for maritime operations with 
    analysis, forecasting, and AI-driven insights capabilities.
    """
    
    def __init__(self, cache_service=None):
        """
        Initializes the calculator with optional cache service.
        """
        self.cache_service = cache_service
    
    async def calculate_pnl(
        self, 
        data: PnLInput, 
        db: AsyncSession, 
        user: User,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict:
        """
        Calculates and records the profit and loss of a voyage or commercial operation
        with advanced financial analysis.
        
        Args:
            data: PnLInput (revenue, costs, details)
            db: AsyncSession
            user: Current user (for traceability)
            background_tasks: Optional background tasks for additional analysis
            
        Returns:
            Dictionary with PnL and detailed financial analysis
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Basic calculation
            net_profit = round(data.revenue - data.total_costs, 2)
            profit_margin = round((net_profit / data.revenue * 100), 2) if data.revenue > 0 else 0
            
            # Get vessel data if available
            vessel_type = "UNKNOWN"
            vessel_name = None
            
            if data.voyage_id:
                # Try to get vessel information through voyage
                voyage_stmt = select(Voyage).where(Voyage.id == data.voyage_id)
                voyage_result = await db.execute(voyage_stmt)
                voyage = voyage_result.scalar_one_or_none()
                
                if voyage and voyage.vessel_id:
                    vessel_stmt = select(Vessel).where(Vessel.id == voyage.vessel_id)
                    vessel_result = await db.execute(vessel_stmt)
                    vessel = vessel_result.scalar_one_or_none()
                    
                    if vessel:
                        vessel_type = vessel.vessel_type
                        vessel_name = vessel.name
            
            # Calculate cost distribution
            total = data.total_costs if data.total_costs > 0 else 1  # Avoid division by zero
            cost_distribution = {
                "fuel_cost": round((data.fuel_cost / total * 100), 2),
                "port_fees": round((data.port_fees / total * 100), 2),
                "delay_penalties": round((data.delay_penalties / total * 100), 2),
                "other_costs": round((data.other_costs / total * 100), 2)
            }
            
            # Compare with industry benchmarks
            benchmark_comparison = {}
            if vessel_type in PROFITABILITY_BENCHMARKS:
                industry_benchmark = PROFITABILITY_BENCHMARKS[vessel_type]
                benchmark_comparison = {
                    "industry_benchmark": industry_benchmark,
                    "difference": round(profit_margin - industry_benchmark, 2),
                    "performance": "ABOVE_AVERAGE" if profit_margin > industry_benchmark else 
                                 "AVERAGE" if profit_margin >= industry_benchmark * 0.9 else 
                                 "BELOW_AVERAGE"
                }
            
            # Compare cost distribution with reference (if available)
            cost_efficiency = {}
            if vessel_type in COST_DISTRIBUTION_REFERENCE:
                reference = COST_DISTRIBUTION_REFERENCE[vessel_type]
                cost_efficiency = {
                    "fuel_efficiency": "EFFICIENT" if cost_distribution["fuel_cost"] <= reference["fuel_cost"] else "INEFFICIENT",
                    "port_efficiency": "EFFICIENT" if cost_distribution["port_fees"] <= reference["port_fees"] else "INEFFICIENT"
                }
            
            # Create comprehensive PnL record with additional metrics
            record = PnLRecord(
                id=request_id,
                user_id=user.id,
                voyage_id=data.voyage_id,
                vessel_type=vessel_type,
                vessel_name=vessel_name,
                revenue=data.revenue,
                fuel_cost=data.fuel_cost,
                port_fees=data.port_fees,
                delay_penalties=data.delay_penalties,
                other_costs=data.other_costs,
                total_costs=data.total_costs,
                net_profit=net_profit,
                profit_margin=profit_margin,
                cost_distribution=cost_distribution,
                benchmark_comparison=benchmark_comparison,
                cost_efficiency=cost_efficiency,
                currency=data.currency,
                notes=data.notes
            )
            
            db.add(record)
            await db.commit()
            await db.refresh(record)
            
            # Invalidate related cache if exists
            if self.cache_service:
                await self.cache_service.delete(f"pnl:user:{user.id}:recent")
                if data.voyage_id:
                    await self.cache_service.delete(f"pnl:voyage:{data.voyage_id}")
                await self.cache_service.delete("pnl:statistics")
            
            # Start background analysis if tasks provided
            if background_tasks and data.voyage_id:
                background_tasks.add_task(
                    self._analyze_profitability_trends,
                    db,
                    user.id,
                    request_id
                )
            
            # Log successful calculation
            processing_time = time.time() - start_time
            api_logger.info(
                f"PnL calculation completed in {processing_time:.2f}s - "
                f"User: {user.id}, Voyage: {data.voyage_id}, "
                f"Net Profit: {net_profit} {data.currency}, Margin: {profit_margin}%"
            )
            
            # Prepare response
            response = {
                "status": "success",
                "request_id": request_id,
                "financial_metrics": {
                    "revenue": data.revenue,
                    "total_costs": data.total_costs,
                    "net_profit": net_profit,
                    "profit_margin": profit_margin,
                },
                "cost_analysis": cost_distribution,
                "record_id": str(record.id)
            }
            
            # Add benchmark comparison if available
            if benchmark_comparison:
                response["benchmark_comparison"] = benchmark_comparison
                
                # Add recommendations if performance is below average
                if benchmark_comparison.get("performance") == "BELOW_AVERAGE":
                    response["recommendations"] = await self._generate_financial_recommendations(
                        vessel_type, 
                        cost_distribution,
                        profit_margin
                    )
            
            return response
            
        except HTTPException as he:
            # Re-raise HTTP exceptions
            api_logger.warning(
                f"Validation error in PnL calculation: {he.detail} - "
                f"User: {user.id}"
            )
            raise he
            
        except Exception as e:
            # Log error and raise generic HTTP exception
            processing_time = time.time() - start_time
            api_logger.error(
                f"Error calculating PnL after {processing_time:.2f}s: {str(e)} - "
                f"User: {user.id}, Data: {json.dumps(data.dict())}"
            )
            raise HTTPException(status_code=500, detail="Failed to calculate PnL")
    
    async def get_user_pnl_records(
        self, 
        user_id: int, 
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        voyage_id: Optional[int] = None,
        vessel_type: Optional[str] = None,
        limit: int = 100,
        cache_service = None
    ) -> List[PnLRecord]:
        """
        Retrieves PnL records for a user with optional filters.
        
        Args:
            user_id: User ID
            db: AsyncSession
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            voyage_id: Optional voyage ID for filtering
            vessel_type: Optional vessel type for filtering
            limit: Limit of records to return
            cache_service: Optional cache service
            
        Returns:
            List of PnL records
        """
        try:
            # Create cache key based on parameters
            cache_key = None
            if cache_service and not any([start_date, end_date, voyage_id, vessel_type]):
                cache_key = f"pnl:user:{user_id}:recent:{limit}"
                cached_data = await cache_service.get(cache_key)
                if cached_data:
                    return cached_data
            
            # Build query with filters
            stmt = select(PnLRecord).where(PnLRecord.user_id == user_id)
            
            if start_date:
                stmt = stmt.where(PnLRecord.created_at >= start_date)
            if end_date:
                stmt = stmt.where(PnLRecord.created_at <= end_date)
            if voyage_id:
                stmt = stmt.where(PnLRecord.voyage_id == voyage_id)
            if vessel_type:
                stmt = stmt.where(PnLRecord.vessel_type == vessel_type)
            
            # Sort by created date descending and limit results
            stmt = stmt.order_by(desc(PnLRecord.created_at)).limit(limit)
            
            # Execute query
            result = await db.execute(stmt)
            records = result.scalars().all()
            
            # Store in cache if applicable
            if cache_key and cache_service:
                # Serialize for cache
                serialized = [
                    {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
                    for record in records
                ]
                await cache_service.set(cache_key, serialized, expire=300)  # 5 minutes
            
            return records
            
        except Exception as e:
            api_logger.error(f"Error fetching PnL records for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error fetching PnL data")
    
    async def get_pnl_statistics(
        self, 
        db: AsyncSession, 
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        cache_service = None
    ) -> Dict:
        """
        Generates detailed statistics about financial performance.
        
        Args:
            db: AsyncSession
            user_id: Filter by user (optional)
            organization_id: Filter by organization (optional)
            start_date: Start date for analysis period
            end_date: End date for analysis period
            cache_service: Optional cache service
            
        Returns:
            Dictionary with financial statistics
        """
        try:
            # Try to get from cache first
            cache_key = None
            if cache_service and not any([start_date, end_date]):
                cache_key = f"pnl:statistics:{user_id or 'all'}:{organization_id or 'all'}"
                cached_data = await cache_service.get(cache_key)
                if cached_data:
                    return cached_data
            
            # Default date range: last 12 months
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=365)
            
            # Build base query
            base_query = select(PnLRecord).where(
                PnLRecord.created_at.between(start_date, end_date)
            )
            
            # Apply filters if provided
            if user_id:
                base_query = base_query.where(PnLRecord.user_id == user_id)
                
            # Add organization filter if implemented
            if organization_id:
                # This assumes a relationship between users and organizations
                # base_query = base_query.join(User).where(User.organization_id == organization_id)
                pass
            
            # 1. Total revenue, costs, and profit
            financials_query = select(
                func.sum(PnLRecord.revenue).label("total_revenue"),
                func.sum(PnLRecord.total_costs).label("total_costs"),
                func.sum(PnLRecord.net_profit).label("total_profit"),
                func.count(PnLRecord.id).label("record_count")
            ).select_from(PnLRecord).where(
                PnLRecord.created_at.between(start_date, end_date)
            )
            
            if user_id:
                financials_query = financials_query.where(PnLRecord.user_id == user_id)
                
            financials_result = await db.execute(financials_query)
            financials = financials_result.fetchone()
            
            total_revenue = float(financials.total_revenue or 0)
            total_costs = float(financials.total_costs or 0)
            total_profit = float(financials.total_profit or 0)
            record_count = financials.record_count or 0
            
            # Calculate overall profit margin
            overall_margin = round((total_profit / total_revenue * 100), 2) if total_revenue > 0 else 0
            
            # 2. Performance by vessel type
            vessel_query = select(
                PnLRecord.vessel_type,
                func.sum(PnLRecord.revenue).label("revenue"),
                func.sum(PnLRecord.total_costs).label("costs"),
                func.sum(PnLRecord.net_profit).label("profit"),
                func.count(PnLRecord.id).label("record_count")
            ).where(
                PnLRecord.created_at.between(start_date, end_date),
                PnLRecord.vessel_type.isnot(None)
            ).group_by(
                PnLRecord.vessel_type
            )
            
            if user_id:
                vessel_query = vessel_query.where(PnLRecord.user_id == user_id)
                
            vessel_result = await db.execute(vessel_query)
            performance_by_vessel = {}
            
            for row in vessel_result:
                if row.vessel_type:
                    vessel_revenue = float(row.revenue or 0)
                    vessel_margin = round((float(row.profit or 0) / vessel_revenue * 100), 2) if vessel_revenue > 0 else 0
                    
                    # Compare with benchmark if available
                    benchmark = PROFITABILITY_BENCHMARKS.get(row.vessel_type)
                    benchmark_comparison = None
                    
                    if benchmark:
                        benchmark_comparison = {
                            "benchmark": benchmark,
                            "difference": round(vessel_margin - benchmark, 2),
                            "status": "ABOVE" if vessel_margin > benchmark else 
                                    "ON_TARGET" if vessel_margin >= benchmark * 0.9 else 
                                    "BELOW"
                        }
                    
                    performance_by_vessel[row.vessel_type] = {
                        "revenue": float(row.revenue or 0),
                        "costs": float(row.costs or 0),
                        "profit": float(row.profit or 0),
                        "margin": vessel_margin,
                        "record_count": row.record_count,
                        "benchmark_comparison": benchmark_comparison
                    }
            
            # 3. Monthly profit trend
            trend_query = select(
                func.extract('year', PnLRecord.created_at).label('year'),
                func.extract('month', PnLRecord.created_at).label('month'),
                func.sum(PnLRecord.revenue).label('revenue'),
                func.sum(PnLRecord.total_costs).label('costs'),
                func.sum(PnLRecord.net_profit).label('profit')
            ).where(
                PnLRecord.created_at.between(start_date, end_date)
            ).group_by(
                func.extract('year', PnLRecord.created_at),
                func.extract('month', PnLRecord.created_at)
            ).order_by(
                func.extract('year', PnLRecord.created_at),
                func.extract('month', PnLRecord.created_at)
            )
            
            if user_id:
                trend_query = trend_query.where(PnLRecord.user_id == user_id)
                
            trend_result = await db.execute(trend_query)
            monthly_trend = []
            
            for row in trend_result:
                month_data = {
                    "year": int(row.year),
                    "month": int(row.month),
                    "revenue": float(row.revenue or 0),
                    "costs": float(row.costs or 0),
                    "profit": float(row.profit or 0),
                    "margin": round((float(row.profit or 0) / float(row.revenue or 1) * 100), 2)
                }
                monthly_trend.append(month_data)
            
            # 4. Cost breakdown analysis
            # Average cost distribution across all records
            avg_fuel_cost = 0
            avg_port_fees = 0
            avg_delay_penalties = 0
            avg_other_costs = 0
            
            if record_count > 0:
                cost_query = select(
                    func.avg(PnLRecord.fuel_cost / PnLRecord.total_costs * 100).label('avg_fuel_pct'),
                    func.avg(PnLRecord.port_fees / PnLRecord.total_costs * 100).label('avg_port_pct'),
                    func.avg(PnLRecord.delay_penalties / PnLRecord.total_costs * 100).label('avg_delay_pct'),
                    func.avg(PnLRecord.other_costs / PnLRecord.total_costs * 100).label('avg_other_pct')
                ).where(
                    PnLRecord.created_at.between(start_date, end_date),
                    PnLRecord.total_costs > 0
                )
                
                if user_id:
                    cost_query = cost_query.where(PnLRecord.user_id == user_id)
                    
                cost_result = await db.execute(cost_query)
                cost_avg = cost_result.fetchone()
                
                if cost_avg:
                    avg_fuel_cost = round(float(cost_avg.avg_fuel_pct or 0), 2)
                    avg_port_fees = round(float(cost_avg.avg_port_pct or 0), 2)
                    avg_delay_penalties = round(float(cost_avg.avg_delay_pct or 0), 2)
                    avg_other_costs = round(float(cost_avg.avg_other_pct or 0), 2)
            
            # Assemble all statistics
            statistics = {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "summary": {
                    "total_revenue": total_revenue,
                    "total_costs": total_costs,
                    "total_profit": total_profit,
                    "overall_margin": overall_margin,
                    "record_count": record_count
                },
                "performance_by_vessel": performance_by_vessel,
                "monthly_trend": monthly_trend,
                "cost_analysis": {
                    "avg_fuel_cost_pct": avg_fuel_cost,
                    "avg_port_fees_pct": avg_port_fees,
                    "avg_delay_penalties_pct": avg_delay_penalties,
                    "avg_other_costs_pct": avg_other_costs
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Store in cache if applicable
            if cache_key and cache_service:
                await cache_service.set(cache_key, statistics, expire=1800)  # 30 minutes
            
            return statistics
            
        except Exception as e:
            api_logger.error(f"Error generating PnL statistics: {str(e)}")
            raise HTTPException(status_code=500, detail="Error generating financial statistics")
    
    async def generate_pnl_report(
        self,
        db: AsyncSession,
        user: User,
        start_date: datetime,
        end_date: datetime,
        vessel_types: Optional[List[str]] = None,
        voyage_ids: Optional[List[int]] = None,
        report_format: str = "detailed"
    ) -> PnLReport:
        """
        Generates a detailed financial performance report for a specific period.
        
        Args:
            db: AsyncSession
            user: Current user
            start_date: Report start date
            end_date: Report end date
            vessel_types: Optional list of vessel types to filter
            voyage_ids: Optional list of voyage IDs to filter
            report_format: Report format ('summary', 'detailed', 'analysis')
            
        Returns:
            PnLReport object with results
        """
        try:
            # Build base query
            query = select(PnLRecord).where(
                PnLRecord.created_at.between(start_date, end_date)
            )
            
            # Filter by user unless they're an admin
            if user.role != UserRole.admin:
                query = query.where(PnLRecord.user_id == user.id)
            
            # Apply additional filters
            if vessel_types:
                query = query.where(PnLRecord.vessel_type.in_(vessel_types))
                
            if voyage_ids:
                query = query.where(PnLRecord.voyage_id.in_(voyage_ids))
            
            # Execute query
            result = await db.execute(query)
            records = result.scalars().all()
            
            if not records:
                return PnLReport(
                    report_id=str(uuid.uuid4()),
                    start_date=start_date,
                    end_date=end_date,
                    generated_at=datetime.utcnow(),
                    generated_by=user.username,
                    total_records=0,
                    total_revenue=0,
                    total_costs=0,
                    total_profit=0,
                    format=report_format,
                    summary="No financial records found for the specified period."
                )
            
            # Calculate financial metrics
            total_revenue = sum(record.revenue for record in records)
            total_costs = sum(record.total_costs for record in records)
            total_profit = sum(record.net_profit for record in records)
            overall_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            # Group by vessel type
            performance_by_vessel = {}
            for record in records:
                vessel_type = record.vessel_type or "UNKNOWN"
                
                if vessel_type not in performance_by_vessel:
                    performance_by_vessel[vessel_type] = {
                        "revenue": 0,
                        "costs": 0,
                        "profit": 0,
                        "count": 0
                    }
                
                performance_by_vessel[vessel_type]["revenue"] += record.revenue
                performance_by_vessel[vessel_type]["costs"] += record.total_costs
                performance_by_vessel[vessel_type]["profit"] += record.net_profit
                performance_by_vessel[vessel_type]["count"] += 1
            
            # Calculate margins for each vessel type
            for vessel_type, data in performance_by_vessel.items():
                data["margin"] = (data["profit"] / data["revenue"] * 100) if data["revenue"] > 0 else 0
                
                # Add benchmark comparison if available
                if vessel_type in PROFITABILITY_BENCHMARKS:
                    benchmark = PROFITABILITY_BENCHMARKS[vessel_type]
                    data["benchmark"] = benchmark
                    data["benchmark_difference"] = data["margin"] - benchmark
                    data["benchmark_status"] = (
                        "ABOVE_TARGET" if data["margin"] > benchmark else
                        "ON_TARGET" if data["margin"] >= benchmark * 0.9 else
                        "BELOW_TARGET"
                    )
            
            # Calculate average cost distribution
            avg_cost_distribution = {
                "fuel_cost": 0,
                "port_fees": 0,
                "delay_penalties": 0,
                "other_costs": 0
            }
            
            if records:
                total_fuel = sum(record.fuel_cost for record in records)
                total_port = sum(record.port_fees for record in records)
                total_delay = sum(record.delay_penalties for record in records)
                total_other = sum(record.other_costs for record in records)
                
                if total_costs > 0:
                    avg_cost_distribution = {
                        "fuel_cost": round((total_fuel / total_costs * 100), 2),
                        "port_fees": round((total_port / total_costs * 100), 2),
                        "delay_penalties": round((total_delay / total_costs * 100), 2),
                        "other_costs": round((total_other / total_costs * 100), 2)
                    }
            
            # Generate AI-based summary if enough data
            summary = ""
            if len(records) > 5:
                try:
                    summary_prompt = (
                        f"Generate a concise professional financial summary with these key metrics:\n"
                        f"- Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n"
                        f"- Total Revenue: ${total_revenue:,.2f}\n"
                        f"- Total Costs: ${total_costs:,.2f}\n"
                        f"- Net Profit: ${total_profit:,.2f}\n"
                        f"- Overall Margin: {overall_margin:.2f}%\n"
                        f"- Vessel Types: {', '.join(performance_by_vessel.keys())}\n"
                        f"- Total Transactions: {len(records)}\n\n"
                        f"Focus on key financial trends, performance relative to industry benchmarks, "
                        f"and provide 1-2 actionable recommendations for improving profitability."
                    )
                    
                    ai_response = await query_ai_engine(prompt=summary_prompt)
                    if isinstance(ai_response, dict) and 'response' in ai_response:
                        summary = ai_response['response']
                    elif isinstance(ai_response, str):
                        summary = ai_response
                except Exception as e:
                    api_logger.error(f"Error generating AI summary for financial report: {str(e)}")
                    summary = (
                        f"Financial performance report for {start_date.strftime('%Y-%m-%d')} to "
                        f"{end_date.strftime('%Y-%m-%d')}. Total revenue: ${total_revenue:,.2f}, "
                        f"total costs: ${total_costs:,.2f}, resulting in net profit of ${total_profit:,.2f} "
                        f"with an overall margin of {overall_margin:.2f}%."
                    )
            
            # Build the report
            report = PnLReport(
                report_id=str(uuid.uuid4()),
                start_date=start_date,
                end_date=end_date,
                generated_at=datetime.utcnow(),
                generated_by=user.username,
                total_records=len(records),
                total_revenue=total_revenue,
                total_costs=total_costs,
                total_profit=total_profit,
                overall_margin=overall_margin,
                vessel_performance=performance_by_vessel,
                cost_distribution=avg_cost_distribution,
                format=report_format,
                summary=summary
            )
            
            # Include detailed records only if detailed format is requested
            if report_format == "detailed":
                report.records = records
            
            # Add trend analysis for analysis format
            if report_format == "analysis":
                # Group by month for trend analysis
                monthly_data = {}
                for record in records:
                    month_key = record.created_at.strftime("%Y-%m")
                    
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {
                            "year": record.created_at.year,
                            "month": record.created_at.month,
                            "revenue": 0,
                            "costs": 0,
                            "profit": 0
                        }
                    
                    monthly_data[month_key]["revenue"] += record.revenue
                    monthly_data[month_key]["costs"] += record.total_costs
                    monthly_data[month_key]["profit"] += record.net_profit
                
                # Calculate margins and sort by date
                trend_analysis = []
                for month_key, data in sorted(monthly_data.items()):
                    data["margin"] = (data["profit"] / data["revenue"] * 100) if data["revenue"] > 0 else 0
                    trend_analysis.append(data)
                
                report.trend_analysis = trend_analysis
            
            return report
            
        except Exception as e:
            api_logger.error(f"Error generating financial report: {str(e)}")
            raise HTTPException(status_code=500, detail="Error generating financial report")
    
    async def _analyze_profitability_trends(
        self,
        db: AsyncSession,
        user_id: int,
        new_record_id: str
    ) -> None:
        """
        Analyzes profitability trends for a user and generates financial forecasts.
        This function is designed to run in the background.
        
        Args:
            db: AsyncSession
            user_id: User ID to analyze
            new_record_id: ID of the new record that triggered the analysis
        """
        try:
            # Get historical records for this user (last 20)
            stmt = select(PnLRecord).where(
                PnLRecord.user_id == user_id
            ).order_by(
                desc(PnLRecord.created_at)
            ).limit(20)
            
            result = await db.execute(stmt)
            records = result.scalars().all()
            
            if len(records) < 5:
                # We need at least 5 records for meaningful analysis
                return
            
            # Extract financial metrics
            profit_margins = [record.profit_margin for record in records if record.profit_margin is not None]
            
            # If we have enough profit margin data, calculate trend
            if len(profit_margins) >= 5:
                # Simple moving average for prediction
                recent_values = profit_margins[:5]  # Last 5 entries (most recent first)
                predicted_value = sum(recent_values) / len(recent_values)
                
                # Determine trend (increasing, decreasing, stable)
                first_half = profit_margins[len(profit_margins)//2:]  # Older values
                second_half = profit_margins[:len(profit_margins)//2]  # Newer values
                
                first_half_avg = sum(first_half) / len(first_half)
                second_half_avg = sum(second_half) / len(second_half)
                
                if second_half_avg > first_half_avg * 1.05:
                    trend = "IMPROVING"
                elif second_half_avg < first_half_avg * 0.95:
                    trend = "DECLINING"
                else:
                    trend = "STABLE"
                
                # Save forecast to database
                forecast = PnLForecast(
                    user_id=user_id,
                    based_on_record_id=new_record_id,
                    forecast_type="PROFIT_MARGIN",
                    predicted_value=predicted_value,
                    confidence=0.8,  # Fixed confidence value for this example
                    trend=trend,
                    forecast_period_days=90,
                    data_points_used=len(profit_margins)
                )
                
                db.add(forecast)
                await db.commit()
                
                api_logger.info(
                    f"Generated financial forecast for user {user_id}: "
                    f"Profit margin trend: {trend}, "
                    f"Predicted value: {predicted_value:.2f}%"
                )
        
        except Exception as e:
            api_logger.error(f"Error in background financial trend analysis: {str(e)}")
    
    async def _generate_financial_recommendations(
        self,
        vessel_type: str,
        cost_distribution: Dict,
        profit_margin: float
    ) -> List[str]:
        """
        Generates recommendations to improve financial performance.
        
        Args:
            vessel_type: Vessel type
            cost_distribution: Cost breakdown percentages
            profit_margin: Current profit margin
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Get benchmark for this vessel type
        benchmark = PROFITABILITY_BENCHMARKS.get(vessel_type)
        if not benchmark:
            # Generic recommendations if no benchmark exists
            recommendations.append(
                "Consider conducting a detailed cost analysis to identify potential areas for optimization."
            )
            recommendations.append(
                "Implement a structured voyage profitability tracking system to monitor performance metrics."
            )
            return recommendations
        
        # Calculate gap to benchmark
        margin_gap = benchmark - profit_margin
        
        # Recommendations based on margin gap
        if margin_gap > 10:
            recommendations.append(
                f"Your profit margin is significantly below the industry benchmark of {benchmark}%. "
                "Consider a comprehensive financial review focusing on both revenue optimization and cost reduction."
            )
        elif margin_gap > 5:
            recommendations.append(
                f"Your profit margin is {margin_gap:.2f}% below the industry benchmark of {benchmark}%. "
                "Focus on optimizing your highest cost categories to improve overall profitability."
            )
        else:
            recommendations.append(
                f"Your profit margin is {margin_gap:.2f}% below the industry benchmark of {benchmark}%. "
                "Minor financial adjustments may help achieve industry-standard profitability."
            )
        
        # Get reference cost distribution if available
        reference = COST_DISTRIBUTION_REFERENCE.get(vessel_type)
        if reference:
            # Check which cost categories are above reference
            if "fuel_cost" in cost_distribution and cost_distribution["fuel_cost"] > reference["fuel_cost"]:
                excess = cost_distribution["fuel_cost"] - reference["fuel_cost"]
                recommendations.append(
                    f"Fuel costs are {excess:.2f}% higher than industry benchmark. "
                    "Consider fuel efficiency measures like slow steaming, hull cleaning, or exploring alternative fuels."
                )
                
            if "port_fees" in cost_distribution and cost_distribution["port_fees"] > reference["port_fees"]:
                excess = cost_distribution["port_fees"] - reference["port_fees"]
                recommendations.append(
                    f"Port fees are {excess:.2f}% higher than industry benchmark. "
                    "Review port selection strategy and consider negotiating long-term agreements with frequent ports."
                )
        
        # Add recommendations on delay penalties if significant
        if "delay_penalties" in cost_distribution and cost_distribution["delay_penalties"] > 5:
            recommendations.append(
                f"Delay penalties represent {cost_distribution['delay_penalties']:.2f}% of your costs. "
                "Improve scheduling accuracy and implement a proactive delay management system."
            )
        
        # If no specific recommendations, provide general ones
        if not recommendations:
            recommendations.append(
                "Regular financial performance monitoring and voyage profitability analysis can help identify optimization opportunities."
            )
        
        return recommendations


# Create calculator instance
pnl_calculator = PnLCalculator()

# Main wrapper function to calculate PnL
async def calculate_pnl(
    data: PnLInput,
    db: AsyncSession,
    user: User,
    background_tasks: Optional[BackgroundTasks] = None
) -> Dict:
    """
    Facade function to calculate profit and loss.
    
    Args:
        data: PnLInput (revenue, costs, details)
        db: AsyncSession
        user: Current user
        background_tasks: Optional background tasks
        
    Returns:
        Dictionary with PnL and analysis results.
    """
    # Get cache service if available
    try:
        cache_service = await get_finance_cache()
    except:
        cache_service = None
    
    calculator = PnLCalculator(cache_service)
    return await calculator.calculate_pnl(data, db, user, background_tasks)

# Wrapper function to get user PnL records
async def get_user_pnl_records(
    user_id: int,
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    voyage_id: Optional[int] = None,
    vessel_type: Optional[str] = None,
    limit: int = 100
) -> List:
    """
    Facade function to get user PnL records.
    
    Args:
        user_id: User ID
        db: AsyncSession
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        voyage_id: Optional voyage ID for filtering
        vessel_type: Optional vessel type for filtering
        limit: Limit of records to return
        
    Returns:
        List of PnL records
    """
    # Get cache service if available
    try:
        cache_service = await get_finance_cache()
    except:
        cache_service = None
    
    calculator = PnLCalculator(cache_service)
    return await calculator.get_user_pnl_records(
        user_id, db, start_date, end_date, voyage_id, vessel_type, limit, cache_service
    )

# Wrapper function to generate PnL report
async def generate_pnl_report(
    db: AsyncSession,
    user: User,
    start_date: datetime,
    end_date: datetime,
    vessel_types: Optional[List[str]] = None,
    voyage_ids: Optional[List[int]] = None,
    report_format: str = "detailed"
) -> PnLReport:
    """
    Facade function to generate financial report.
    
    Args:
        db: AsyncSession
        user: Current user
        start_date: Report start date
        end_date: Report end date
        vessel_types: Optional list of vessel types to filter
        voyage_ids: Optional list of voyage IDs to filter
        report_format: Report format ('summary', 'detailed', 'analysis')
        
    Returns:
        PnLReport object with results
    """
    calculator = PnLCalculator()
    return await calculator.generate_pnl_report(
        db, user, start_date, end_date, vessel_types, voyage_ids, report_format
    )

# Wrapper function to get PnL statistics
async def get_pnl_statistics(
    db: AsyncSession,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict:
    """
    Facade function to get financial statistics.
    
    Args:
        db: AsyncSession
        user_id: Filter by user (optional)
        organization_id: Filter by organization (optional)
        start_date: Start date for analysis period
        end_date: End date for analysis period
        
    Returns:
        Dictionary with financial statistics
    """
    # Get cache service if available
    try:
        cache_service = await get_finance_cache()
    except:
        cache_service = None
    
    calculator = PnLCalculator(cache_service)
    return await calculator.get_pnl_statistics(db, user_id, organization_id, start_date, end_date, cache_service)