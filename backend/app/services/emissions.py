# Path: backend/app/services/emissions.py

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
from sqlalchemy.types import Float

from app.models.emissions import EmissionRecord, EmissionForecast, EmissionBenchmark
from app.models.vessel import Vessel
from app.models.voyage import Voyage
from app.models.user import User, UserRole
from app.schemas.emissions import EmissionInput, EmissionReport, EmissionTarget, EmissionCompliance
from app.core.logging import api_logger
from app.dependencies.redis_cache import get_emission_cache
from app.services.ai_engine import query_ai_engine

# Emission factors in kg per ton of fuel (based on IMO MEPC guidelines)
EMISSION_FACTORS = {
    "HFO": {
        "CO2": 3.114, 
        "SOx": 0.02, 
        "NOx": 0.087, 
        "PM": 0.007,
        "CH4": 0.00006
    },
    "VLSFO": {
        "CO2": 3.151, 
        "SOx": 0.005, 
        "NOx": 0.083, 
        "PM": 0.0068,
        "CH4": 0.00006
    },
    "MGO": {
        "CO2": 3.206, 
        "SOx": 0.0015, 
        "NOx": 0.075, 
        "PM": 0.0017,
        "CH4": 0.00006
    },
    "LNG": {
        "CO2": 2.75, 
        "SOx": 0.0, 
        "NOx": 0.05, 
        "PM": 0.0001,
        "CH4": 0.0123
    },
    "BIOFUEL": {
        "CO2": 1.97,  # Reduced CO2 due to biogenic carbon
        "SOx": 0.0001,
        "NOx": 0.08,
        "PM": 0.001,
        "CH4": 0.00004
    },
    "METHANOL": {
        "CO2": 1.375,
        "SOx": 0.0,
        "NOx": 0.035,
        "PM": 0.0001,
        "CH4": 0.00002
    },
    "HYDROGEN": {
        "CO2": 0.0,
        "SOx": 0.0,
        "NOx": 0.01,
        "PM": 0.0,
        "CH4": 0.0
    },
    "AMMONIA": {
        "CO2": 0.0,
        "SOx": 0.0,
        "NOx": 0.02,
        "PM": 0.0001,
        "CH4": 0.0
    }
}

# IMO regulation thresholds for 2025 (g CO2/ton-nm)
IMO_REGULATIONS_2025 = {
    "BULK_CARRIER": 3.15,
    "TANKER": 4.30,
    "CONTAINER": 2.80,
    "GENERAL_CARGO": 3.45,
    "REFRIGERATED": 5.10,
    "RO_RO": 6.20,
    "LNG_CARRIER": 5.00,
    "CRUISE": 9.00
}

# GWP (Global Warming Potential) for greenhouse gases
GWP_FACTORS = {
    "CO2": 1,
    "CH4": 28,  # Methane - 28 times more potent than CO2 over 100 years
    "N2O": 265  # Nitrous oxide - 265 times more potent than CO2 over 100 years
}

class EmissionCalculator:
    """
    Advanced maritime emission calculator with analysis, prediction, and
    AI-based recommendation capabilities.
    """
    
    def __init__(self, cache_service=None):
        """
        Initializes the calculator with optional cache services.
        """
        self.cache_service = cache_service
    
    async def calculate_emissions(
        self, 
        data: EmissionInput, 
        db: AsyncSession, 
        user: User,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict:
        """
        Calculates and stores emissions based on fuel consumption.
        
        Args:
            data: EmissionInput (voyage and consumption information)
            db: AsyncSession
            user: Current user (to track record ownership)
            background_tasks: Background tasks for additional analysis
            
        Returns:
            Dictionary with emission results.
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Validate and get emission factors
            fuel_type_upper = data.fuel_type.upper()
            factors = EMISSION_FACTORS.get(fuel_type_upper)
            if not factors:
                supported_fuels = ", ".join(EMISSION_FACTORS.keys())
                raise HTTPException(
                    status_code=400, 
                    detail=f"Unsupported fuel type. Supported types: {supported_fuels}"
                )
            
            # Check if the vessel exists and get its data
            vessel = None
            if data.vessel_id:
                vessel_stmt = select(Vessel).where(Vessel.id == data.vessel_id)
                vessel_result = await db.execute(vessel_stmt)
                vessel = vessel_result.scalar_one_or_none()
                
                if not vessel:
                    raise HTTPException(status_code=404, detail="Vessel not found")
                
                # Use vessel name from database if available
                vessel_name = vessel.name
                vessel_type = vessel.vessel_type
                vessel_deadweight = vessel.deadweight_tonnage
            else:
                # Use provided name and default values
                vessel_name = data.vessel_name
                vessel_type = data.vessel_type or "UNKNOWN"
                vessel_deadweight = data.deadweight_tonnage or 0
            
            # Calculate basic emissions (kg)
            emissions = {
                "CO2": round(data.fuel_consumed_tons * factors["CO2"] * 1000, 2),  # Convert to kg
                "SOx": round(data.fuel_consumed_tons * factors["SOx"] * 1000, 2),
                "NOx": round(data.fuel_consumed_tons * factors["NOx"] * 1000, 2),
                "PM": round(data.fuel_consumed_tons * factors.get("PM", 0) * 1000, 2),
                "CH4": round(data.fuel_consumed_tons * factors.get("CH4", 0) * 1000, 2)
            }
            
            # Calculate CO2 equivalent (includes effect of other gases)
            co2e = (
                emissions["CO2"] * GWP_FACTORS["CO2"] + 
                emissions["CH4"] * GWP_FACTORS["CH4"]
            )
            
            # Calculate efficiency metrics
            distance_km = data.distance_nm * 1.852  # Nautical miles to kilometers
            
            efficiency_metrics = {}
            if data.distance_nm > 0:
                # Emissions per distance
                efficiency_metrics["CO2_per_nm"] = round(emissions["CO2"] / data.distance_nm, 3)
                efficiency_metrics["CO2_per_km"] = round(emissions["CO2"] / distance_km, 3)
                
                # Transport efficiency (if cargo is provided)
                if data.cargo_tons and data.cargo_tons > 0:
                    # Emissions per ton-kilometer (industry standard measure)
                    efficiency_metrics["CO2_per_ton_km"] = round(emissions["CO2"] / (data.cargo_tons * distance_km), 3)
                    efficiency_metrics["CO2_per_ton_nm"] = round(emissions["CO2"] / (data.cargo_tons * data.distance_nm), 3)
                    
                    # Transport carbon intensity (gCO2/ton-nm)
                    efficiency_metrics["carbon_intensity"] = round(emissions["CO2"] / (data.cargo_tons * data.distance_nm), 3)
            
            # Evaluate IMO regulation compliance if sufficient data
            compliance_status = None
            if vessel_type in IMO_REGULATIONS_2025 and "carbon_intensity" in efficiency_metrics:
                threshold = IMO_REGULATIONS_2025[vessel_type]
                carbon_intensity = efficiency_metrics["carbon_intensity"]
                
                if carbon_intensity <= threshold:
                    compliance_status = "COMPLIANT"
                else:
                    # Calculate percentage above threshold
                    excess_percentage = ((carbon_intensity - threshold) / threshold) * 100
                    if excess_percentage < 10:
                        compliance_status = "BORDERLINE"
                    else:
                        compliance_status = "NON_COMPLIANT"
                
                efficiency_metrics["imo_threshold"] = threshold
                efficiency_metrics["compliance_status"] = compliance_status
                efficiency_metrics["excess_percentage"] = round(excess_percentage, 2) if compliance_status != "COMPLIANT" else 0
            
            # Create and save emission record
            record = EmissionRecord(
                id=request_id,
                user_id=user.id,
                vessel_id=data.vessel_id,
                vessel_name=vessel_name,
                vessel_type=vessel_type,
                deadweight_tonnage=vessel_deadweight,
                voyage_id=data.voyage_id,
                route_from=data.route_from,
                route_to=data.route_to,
                fuel_type=data.fuel_type,
                fuel_consumed_tons=data.fuel_consumed_tons,
                distance_nm=data.distance_nm,
                cargo_tons=data.cargo_tons,
                co2_kg=emissions["CO2"],
                sox_kg=emissions["SOx"],
                nox_kg=emissions["NOx"],
                pm_kg=emissions["PM"],
                ch4_kg=emissions["CH4"],
                co2e_kg=co2e,
                efficiency_metrics=efficiency_metrics,
                compliance_status=compliance_status,
                voyage_date=data.voyage_date,
                notes=data.notes
            )
            
            db.add(record)
            await db.commit()
            await db.refresh(record)
            
            # Invalidate related cache if it exists
            if self.cache_service:
                await self.cache_service.delete(f"emissions:user:{user.id}:recent")
                await self.cache_service.delete(f"emissions:vessel:{data.vessel_id}:recent")
                await self.cache_service.delete("emissions:statistics")
            
            # Start background analysis if background tasks are provided
            if background_tasks and data.vessel_id:
                background_tasks.add_task(
                    self._analyze_emission_trends,
                    db,
                    data.vessel_id,
                    request_id
                )
            
            # Log successful calculation
            processing_time = time.time() - start_time
            api_logger.info(
                f"Emission calculation completed in {processing_time:.2f}s - "
                f"User: {user.id}, Vessel: {vessel_name}, "
                f"CO2: {emissions['CO2']} kg"
            )
            
            # Prepare response
            response = {
                "status": "success",
                "request_id": request_id,
                "emissions": {
                    "CO2_kg": emissions["CO2"],
                    "SOx_kg": emissions["SOx"],
                    "NOx_kg": emissions["NOx"],
                    "PM_kg": emissions["PM"],
                    "CH4_kg": emissions["CH4"],
                    "CO2e_kg": co2e
                },
                "efficiency": efficiency_metrics,
                "record_id": str(record.id)
            }
            
            # Add recommendations based on compliance
            if compliance_status == "NON_COMPLIANT" or compliance_status == "BORDERLINE":
                response["recommendations"] = await self._generate_recommendations(
                    vessel_type, 
                    data.fuel_type,
                    efficiency_metrics
                )
            
            return response
            
        except HTTPException as he:
            # Re-raise HTTP exceptions
            api_logger.warning(
                f"Validation error in emission calculation: {he.detail} - "
                f"User: {user.id}"
            )
            raise he
            
        except Exception as e:
            # Log error and raise generic HTTP exception
            processing_time = time.time() - start_time
            api_logger.error(
                f"Error calculating emissions after {processing_time:.2f}s: {str(e)} - "
                f"User: {user.id}, Data: {json.dumps(data.dict())}"
            )
            raise HTTPException(status_code=500, detail="Failed to calculate emissions")
    
    async def get_user_emissions(
        self, 
        user_id: int, 
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        vessel_id: Optional[int] = None,
        fuel_type: Optional[str] = None,
        limit: int = 100,
        cache_service = None
    ) -> List[EmissionRecord]:
        """
        Retrieves emission records for a user with optional filters.
        
        Args:
            user_id: User ID
            db: AsyncSession
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            vessel_id: Optional vessel ID for filtering
            fuel_type: Optional fuel type for filtering
            limit: Limit of records to return
            cache_service: Optional cache service
            
        Returns:
            List of emission records
        """
        try:
            # Create cache key based on parameters
            cache_key = None
            if cache_service and not any([start_date, end_date, vessel_id, fuel_type]):
                cache_key = f"emissions:user:{user_id}:recent:{limit}"
                cached_data = await cache_service.get(cache_key)
                if cached_data:
                    return cached_data
            
            # Build query with filters
            stmt = select(EmissionRecord).where(EmissionRecord.user_id == user_id)
            
            if start_date:
                stmt = stmt.where(EmissionRecord.created_at >= start_date)
            if end_date:
                stmt = stmt.where(EmissionRecord.created_at <= end_date)
            if vessel_id:
                stmt = stmt.where(EmissionRecord.vessel_id == vessel_id)
            if fuel_type:
                stmt = stmt.where(EmissionRecord.fuel_type == fuel_type)
            
            # Sort by created date descending and limit results
            stmt = stmt.order_by(desc(EmissionRecord.created_at)).limit(limit)
            
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
            api_logger.error(f"Error fetching emissions for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Error fetching emission data")
    
    async def get_emission_statistics(
        self, 
        db: AsyncSession, 
        user_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        cache_service = None
    ) -> Dict:
        """
        Generates detailed statistics about emissions.
        
        Args:
            db: AsyncSession
            user_id: Filter by user (optional)
            organization_id: Filter by organization (optional)
            cache_service: Optional cache service
            
        Returns:
            Dictionary with emission statistics
        """
        try:
            # Try to get from cache first
            cache_key = None
            if cache_service:
                cache_key = f"emissions:statistics:{user_id or 'all'}:{organization_id or 'all'}"
                cached_data = await cache_service.get(cache_key)
                if cached_data:
                    return cached_data
            
            # Build base queries
            base_query = select(EmissionRecord)
            
            # Apply filters if provided
            if user_id:
                base_query = base_query.where(EmissionRecord.user_id == user_id)
                
            # Add organization filter if implemented
            if organization_id:
                # This assumes you have a relationship between users and organizations
                # base_query = base_query.join(User).where(User.organization_id == organization_id)
                pass
            
            # 1. Total CO2 emissions
            co2_query = select(func.sum(EmissionRecord.co2_kg)).select_from(EmissionRecord)
            if user_id:
                co2_query = co2_query.where(EmissionRecord.user_id == user_id)
            
            co2_result = await db.execute(co2_query)
            total_co2 = co2_result.scalar_one_or_none() or 0
            
            # 2. Emissions by fuel type
            fuel_query = select(
                EmissionRecord.fuel_type,
                func.sum(EmissionRecord.co2_kg).label("co2_total"),
                func.sum(EmissionRecord.sox_kg).label("sox_total"),
                func.sum(EmissionRecord.nox_kg).label("nox_total"),
                func.count(EmissionRecord.id).label("record_count")
            ).group_by(EmissionRecord.fuel_type)
            
            if user_id:
                fuel_query = fuel_query.where(EmissionRecord.user_id == user_id)
                
            fuel_result = await db.execute(fuel_query)
            emissions_by_fuel = {}
            for row in fuel_result:
                emissions_by_fuel[row.fuel_type] = {
                    "CO2_kg": float(row.co2_total or 0),
                    "SOx_kg": float(row.sox_total or 0),
                    "NOx_kg": float(row.nox_total or 0),
                    "record_count": row.record_count
                }
            
            # 3. Emissions by vessel type
            vessel_query = select(
                EmissionRecord.vessel_type,
                func.sum(EmissionRecord.co2_kg).label("co2_total"),
                func.count(EmissionRecord.id).label("record_count")
            ).group_by(EmissionRecord.vessel_type)
            
            if user_id:
                vessel_query = vessel_query.where(EmissionRecord.user_id == user_id)
                
            vessel_result = await db.execute(vessel_query)
            emissions_by_vessel = {}
            for row in vessel_result:
                if row.vessel_type:  # Ignore records without vessel type
                    emissions_by_vessel[row.vessel_type] = {
                        "CO2_kg": float(row.co2_total or 0),
                        "record_count": row.record_count
                    }
            
            # 4. Monthly emissions trend (last 12 months)
            current_date = datetime.utcnow()
            start_date = current_date - timedelta(days=365)
            
            # This query depends on your database capabilities
            # to extract year and month - this example is for PostgreSQL
            trend_query = select(
                func.extract('year', EmissionRecord.voyage_date).label('year'),
                func.extract('month', EmissionRecord.voyage_date).label('month'),
                func.sum(EmissionRecord.co2_kg).label('co2_total')
            ).where(
                EmissionRecord.voyage_date >= start_date
            ).group_by(
                func.extract('year', EmissionRecord.voyage_date),
                func.extract('month', EmissionRecord.voyage_date)
            ).order_by(
                func.extract('year', EmissionRecord.voyage_date),
                func.extract('month', EmissionRecord.voyage_date)
            )
            
            if user_id:
                trend_query = trend_query.where(EmissionRecord.user_id == user_id)
                
            trend_result = await db.execute(trend_query)
            monthly_trend = []
            for row in trend_result:
                month_data = {
                    "year": int(row.year),
                    "month": int(row.month),
                    "CO2_kg": float(row.co2_total or 0)
                }
                monthly_trend.append(month_data)
            
            # 5. Compliance status
            compliance_query = select(
                EmissionRecord.compliance_status,
                func.count(EmissionRecord.id).label('count')
            ).where(
                EmissionRecord.compliance_status.isnot(None)
            ).group_by(
                EmissionRecord.compliance_status
            )
            
            if user_id:
                compliance_query = compliance_query.where(EmissionRecord.user_id == user_id)
                
            compliance_result = await db.execute(compliance_query)
            compliance_stats = {}
            for row in compliance_result:
                if row.compliance_status:
                    compliance_stats[row.compliance_status] = row.count
            
            # Assemble all statistics
            statistics = {
                "total_co2_kg": float(total_co2),
                "emissions_by_fuel": emissions_by_fuel,
                "emissions_by_vessel_type": emissions_by_vessel,
                "monthly_trend": monthly_trend,
                "compliance_stats": compliance_stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Store in cache if applicable
            if cache_key and cache_service:
                await cache_service.set(cache_key, statistics, expire=1800)  # 30 minutes
            
            return statistics
            
        except Exception as e:
            api_logger.error(f"Error generating emission statistics: {str(e)}")
            raise HTTPException(status_code=500, detail="Error generating emission statistics")
    
    async def generate_emission_report(
        self,
        db: AsyncSession,
        user: User,
        start_date: datetime,
        end_date: datetime,
        vessel_ids: Optional[List[int]] = None,
        report_format: str = "detailed"
    ) -> EmissionReport:
        """
        Generates a detailed emission report for a specific period.
        
        Args:
            db: AsyncSession
            user: Current user
            start_date: Report start date
            end_date: Report end date
            vessel_ids: Optional list of vessel IDs to filter
            report_format: Report format ('summary', 'detailed', 'compliance')
            
        Returns:
            EmissionReport object with results
        """
        try:
            # Build base query
            query = select(EmissionRecord).where(
                EmissionRecord.voyage_date.between(start_date, end_date)
            )
            
            # Filter by user unless they're an admin
            if user.role != UserRole.admin:
                query = query.where(EmissionRecord.user_id == user.id)
            
            # Filter by vessels if specified
            if vessel_ids:
                query = query.where(EmissionRecord.vessel_id.in_(vessel_ids))
            
            # Execute query
            result = await db.execute(query)
            records = result.scalars().all()
            
            if not records:
                return EmissionReport(
                    report_id=str(uuid.uuid4()),
                    start_date=start_date,
                    end_date=end_date,
                    generated_at=datetime.utcnow(),
                    generated_by=user.username,
                    total_records=0,
                    total_co2_kg=0,
                    vessels_count=0,
                    format=report_format,
                    summary="No emission records found for the specified period."
                )
            
            # Calculate metrics for the report
            total_co2 = sum(record.co2_kg for record in records)
            total_sox = sum(record.sox_kg for record in records)
            total_nox = sum(record.nox_kg for record in records)
            total_pm = sum(record.pm_kg for record in records)
            total_ch4 = sum(record.ch4_kg for record in records)
            total_co2e = sum(record.co2e_kg for record in records)
            total_distance = sum(record.distance_nm for record in records)
            total_fuel = sum(record.fuel_consumed_tons for record in records)
            
            # Get unique set of vessels
            unique_vessels = set(record.vessel_id for record in records if record.vessel_id)
            vessels_count = len(unique_vessels)
            
            # Analyze compliance
            compliant_records = [r for r in records if r.compliance_status == "COMPLIANT"]
            non_compliant_records = [r for r in records if r.compliance_status == "NON_COMPLIANT"]
            compliance_percentage = (
                (len(compliant_records) / len(records)) * 100 if records else 0
            )
            
            # Group by fuel type
            fuel_types = {}
            for record in records:
                if record.fuel_type not in fuel_types:
                    fuel_types[record.fuel_type] = {
                        "count": 0,
                        "co2_kg": 0,
                        "fuel_tons": 0
                    }
                
                fuel_types[record.fuel_type]["count"] += 1
                fuel_types[record.fuel_type]["co2_kg"] += record.co2_kg
                fuel_types[record.fuel_type]["fuel_tons"] += record.fuel_consumed_tons
            
            # Generate AI-based summary if enough data
            summary = ""
            if len(records) > 5:
                try:
                    summary_prompt = (
                        f"Generate a concise professional summary of maritime emissions data with these key metrics:\n"
                        f"- Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n"
                        f"- Total CO2: {total_co2:.2f} kg\n"
                        f"- Total SOx: {total_sox:.2f} kg\n"
                        f"- Total NOx: {total_nox:.2f} kg\n"
                        f"- Vessels count: {vessels_count}\n"
                        f"- Compliance rate: {compliance_percentage:.1f}%\n"
                        f"- Total distance: {total_distance} nautical miles\n"
                        f"- Total fuel consumed: {total_fuel} tons\n\n"
                        f"Focus on performance relative to industry standards and any notable trends. "
                        f"Include 1-2 professional recommendations if compliance is below 90%."
                    )
                    
                    ai_response = await query_ai_engine(prompt=summary_prompt)
                    if isinstance(ai_response, dict) and 'response' in ai_response:
                        summary = ai_response['response']
                    elif isinstance(ai_response, str):
                        summary = ai_response
                except Exception as e:
                    api_logger.error(f"Error generating AI summary for emissions report: {str(e)}")
                    summary = (
                        f"Report period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}. "
                        f"Total emissions: {total_co2:.2f} kg CO2 from {vessels_count} vessels over "
                        f"{total_distance} nautical miles. Overall compliance: {compliance_percentage:.1f}%."
                    )
            
            # Build the report
            report = EmissionReport(
                report_id=str(uuid.uuid4()),
                start_date=start_date,
                end_date=end_date,
                generated_at=datetime.utcnow(),
                generated_by=user.username,
                total_records=len(records),
                total_co2_kg=total_co2,
                total_sox_kg=total_sox,
                total_nox_kg=total_nox,
                total_pm_kg=total_pm,
                total_ch4_kg=total_ch4,
                total_co2e_kg=total_co2e,
                total_fuel_tons=total_fuel,
                total_distance_nm=total_distance,
                vessels_count=vessels_count,
                compliant_records=len(compliant_records),
                non_compliant_records=len(non_compliant_records),
                compliance_percentage=compliance_percentage,
                format=report_format,
                summary=summary,
                fuel_breakdown=fuel_types
            )
            
            # Include detailed records only if detailed format is requested
            if report_format == "detailed":
                report.records = records
            
            return report
            
        except Exception as e:
            api_logger.error(f"Error generating emission report: {str(e)}")
            raise HTTPException(status_code=500, detail="Error generating emission report")
    
    async def _analyze_emission_trends(
        self,
        db: AsyncSession,
        vessel_id: int,
        new_record_id: str
    ) -> None:
        """
        Analyzes emission trends for a specific vessel and generates predictions.
        This function is designed to run in the background.
        
        Args:
            db: AsyncSession
            vessel_id: Vessel ID to analyze
            new_record_id: ID of the new record that triggered the analysis
        """
        try:
            # Get historical records for this vessel
            stmt = select(EmissionRecord).where(
                EmissionRecord.vessel_id == vessel_id
            ).order_by(
                EmissionRecord.voyage_date
            ).limit(20)  # Use the last 20 records for analysis
            
            result = await db.execute(stmt)
            records = result.scalars().all()
            
            if len(records) < 5:
                # We need at least 5 records for meaningful analysis
                return
            
            # Extract CO2 emissions and efficiency time series
            dates = [record.voyage_date for record in records]
            co2_values = [record.co2_kg for record in records]
            
            # Extract carbon intensity values if available
            carbon_intensity_values = []
            for record in records:
                if record.efficiency_metrics and "carbon_intensity" in record.efficiency_metrics:
                    carbon_intensity_values.append(record.efficiency_metrics["carbon_intensity"])
            
            # If we have enough carbon intensity data, calculate trend
            if len(carbon_intensity_values) >= 5:
                # Implement prediction logic here - this is a simplified example
                # In a real implementation, you would use more sophisticated techniques
                
                # Example: Simple moving average for prediction
                recent_values = carbon_intensity_values[-5:]
                predicted_value = sum(recent_values) / len(recent_values)
                
                # Determine trend (increasing, decreasing, stable)
                first_half = carbon_intensity_values[:(len(carbon_intensity_values)//2)]
                second_half = carbon_intensity_values[(len(carbon_intensity_values)//2):]
                
                first_half_avg = sum(first_half) / len(first_half)
                second_half_avg = sum(second_half) / len(second_half)
                
                if second_half_avg < first_half_avg * 0.95:
                    trend = "DECREASING"
                elif second_half_avg > first_half_avg * 1.05:
                    trend = "INCREASING"
                else:
                    trend = "STABLE"
                
                # Save prediction to database
                forecast = EmissionForecast(
                    vessel_id=vessel_id,
                    based_on_record_id=new_record_id,
                    prediction_type="CARBON_INTENSITY",
                    predicted_value=predicted_value,
                    confidence=0.8,  # Fixed confidence value for this example
                    trend=trend,
                    forecast_period_days=30,
                    data_points_used=len(carbon_intensity_values)
                )
                
                db.add(forecast)
                await db.commit()
                
                api_logger.info(
                    f"Generated emission forecast for vessel {vessel_id}: "
                    f"Carbon intensity trend: {trend}, "
                    f"Predicted value: {predicted_value:.2f}"
                )
        
        except Exception as e:
            api_logger.error(f"Error in background emission trend analysis: {str(e)}")
    
    async def _generate_recommendations(
        self,
        vessel_type: str,
        fuel_type: str,
        metrics: Dict
    ) -> List[str]:
        """
        Generates recommendations to improve regulatory compliance.
        
        Args:
            vessel_type: Vessel type
            fuel_type: Fuel type
            metrics: Efficiency metrics
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Recommendations based on fuel type
        if fuel_type == "HFO":
            recommendations.append(
                "Consider switching to cleaner fuels like MGO or LNG to reduce SOx and CO2 emissions."
            )
        elif fuel_type == "MGO":
            recommendations.append(
                "While MGO is cleaner than HFO, exploring LNG or biofuels could further reduce emissions."
            )
        
        # Recommendations based on carbon intensity
        if "carbon_intensity" in metrics and "imo_threshold" in metrics:
            excess = metrics["carbon_intensity"] - metrics["imo_threshold"]
            if excess > 0:
                percentage = (excess / metrics["imo_threshold"]) * 100
                
                if percentage > 20:
                    recommendations.append(
                        f"Your carbon intensity is {percentage:.1f}% above IMO 2025 threshold. "
                        "Consider a comprehensive efficiency improvement program including hull cleaning, "
                        "propeller polishing, and voyage optimization."
                    )
                elif percentage > 10:
                    recommendations.append(
                        f"Your carbon intensity is {percentage:.1f}% above IMO 2025 threshold. "
                        "Consider operational measures like slow steaming and weather routing to improve efficiency."
                    )
                else:
                    recommendations.append(
                        f"Your carbon intensity is {percentage:.1f}% above IMO 2025 threshold. "
                        "Minor operational adjustments may help achieve compliance."
                    )
        
        # If no specific recommendations, provide general ones
        if not recommendations:
            recommendations.append(
                "Regular monitoring and voyage optimization can help improve efficiency and reduce emissions."
            )
        
        return recommendations


# Create calculator instance
emission_calculator = EmissionCalculator()

# Main wrapper function to calculate emissions
async def calculate_emissions(
    data: EmissionInput,
    db: AsyncSession,
    user: User,
    background_tasks: Optional[BackgroundTasks] = None
) -> Dict:
    """
    Facade function to calculate emissions.
    
    Args:
        data: EmissionInput (voyage and consumption information)
        db: AsyncSession
        user: Current user
        background_tasks: Optional background tasks
        
    Returns:
        Dictionary with emission results.
    """
    # Get cache service if available
    try:
        cache_service = await get_emission_cache()
    except:
        cache_service = None
    
    calculator = EmissionCalculator(cache_service)
    return await calculator.calculate_emissions(data, db, user, background_tasks)

# Wrapper function to get user emissions
async def get_user_emissions(
    user_id: int,
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    vessel_id: Optional[int] = None,
    fuel_type: Optional[str] = None,
    limit: int = 100
) -> List:
    """
    Facade function to get user emissions.
    
    Args:
        user_id: User ID
        db: AsyncSession
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        vessel_id: Optional vessel ID for filtering
        fuel_type: Optional fuel type for filtering
        limit: Limit of records to return
        
    Returns:
        List of emission records
    """
    # Get cache service if available
    try:
        cache_service = await get_emission_cache()
    except:
        cache_service = None
    
    calculator = EmissionCalculator(cache_service)
    return await calculator.get_user_emissions(
        user_id, db, start_date, end_date, vessel_id, fuel_type, limit, cache_service
    )

# Wrapper function to generate emission report
async def generate_emission_report(
    db: AsyncSession,
    user: User,
    start_date: datetime,
    end_date: datetime,
    vessel_ids: Optional[List[int]] = None,
    report_format: str = "detailed"
) -> EmissionReport:
    """
    Facade function to generate emission report.
    
    Args:
        db: AsyncSession
        user: Current user
        start_date: Report start date
        end_date: Report end date
        vessel_ids: Optional list of vessel IDs to filter
        report_format: Report format ('summary', 'detailed', 'compliance')
        
    Returns:
        EmissionReport object with results
    """
    calculator = EmissionCalculator()
    return await calculator.generate_emission_report(
        db, user, start_date, end_date, vessel_ids, report_format
    )

# Wrapper function to get emission statistics
async def get_emission_statistics(
    db: AsyncSession,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None
) -> Dict:
    """
    Facade function to get emission statistics.
    
    Args:
        db: AsyncSession
        user_id: Filter by user (optional)
        organization_id: Filter by organization (optional)
        
    Returns:
        Dictionary with emission statistics
    """
    # Get cache service if available
    try:
        cache_service = await get_emission_cache()
    except:
        cache_service = None
    
    calculator = EmissionCalculator(cache_service)
    return await calculator.get_emission_statistics(db, user_id, organization_id, cache_service)