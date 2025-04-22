# Path: backend/app/services/voyage_calc.py

import uuid
import time
import json
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.models.vessel import Vessel
from app.models.voyage import Voyage, VoyageCalculation
from app.models.weather import WeatherForecast
from app.models.port import Port
from app.models.user import User
from app.schemas.voyage import (
    VoyageCalculationInput, 
    VoyageCalculationResult,
    VoyagePerformanceMetrics,
    VoyageOptimizationRequest
)
from app.core.logging import api_logger
from app.dependencies.redis_cache import get_voyage_cache
from app.services.weather_service import get_route_weather_forecast
from app.services.vessel_service import get_vessel_consumption_profile
from app.services.ai_engine import query_ai_engine

# Sea state factors affecting fuel consumption (based on Beaufort scale)
SEA_STATE_FACTORS = {
    0: 1.00,  # Calm (0-1 ft)
    1: 1.02,  # Light air (1-2 ft)
    2: 1.05,  # Light breeze (2-3 ft)
    3: 1.08,  # Gentle breeze (3-5 ft)
    4: 1.12,  # Moderate breeze (5-8 ft)
    5: 1.18,  # Fresh breeze (8-13 ft)
    6: 1.25,  # Strong breeze (13-19 ft)
    7: 1.35,  # Near gale (19-23 ft)
    8: 1.45,  # Gale (23-32 ft)
    9: 1.60   # Strong gale (32+ ft)
}

# Wind direction impact factors (relative angle to vessel course)
WIND_DIRECTION_FACTORS = {
    "head": 1.15,      # 0° (directly against)
    "bow": 1.10,       # 45°
    "beam": 1.05,      # 90°
    "quarter": 0.98,   # 135°
    "following": 0.95  # 180° (directly behind)
}

# Current impact factors (knots)
CURRENT_IMPACT = {
    "against": lambda speed: 0.8 * speed,  # Against reduces effective speed
    "with": lambda speed: 0.6 * speed      # With increases effective speed
}

# Regional piracy risk levels and their impact on routes
PIRACY_RISK_REGIONS = {
    "Gulf of Aden": {
        "risk_level": "HIGH",
        "coordinates": [(43.0, 12.0), (51.0, 12.0), (51.0, 16.0), (43.0, 16.0)],  # Simplified polygon
        "speed_recommendation": "HIGH",  # Go faster through these waters
        "routing_impact": "AVOID_WHEN_POSSIBLE"
    },
    "Gulf of Guinea": {
        "risk_level": "HIGH",
        "coordinates": [(8.0, 4.0), (8.0, -2.0), (-5.0, -2.0), (-5.0, 4.0)],
        "speed_recommendation": "HIGH",
        "routing_impact": "CAUTION"
    },
    "Strait of Malacca": {
        "risk_level": "MEDIUM",
        "coordinates": [(100.0, 6.0), (100.0, 1.0), (104.0, 1.0), (104.0, 6.0)],
        "speed_recommendation": "NORMAL",
        "routing_impact": "ESCORT_RECOMMENDED"
    }
}

class VoyageCalculator:
    """
    Advanced maritime voyage calculator with weather integration, optimization,
    and performance analytics capabilities.
    """
    
    def __init__(self, cache_service=None):
        """
        Initializes the calculator with optional cache service.
        """
        self.cache_service = cache_service
    
    async def calculate_eta(
        self, 
        data: VoyageCalculationInput,
        db: Optional[AsyncSession] = None,
        user: Optional[User] = None,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> VoyageCalculationResult:
        """
        Calculates ETA, estimated voyage duration, and fuel consumption with 
        advanced weather integration and optimization.

        Args:
            data: Voyage information (ports, speed, consumption, distance)
            db: Optional AsyncSession for storing results
            user: Optional User for record attribution
            background_tasks: Optional background tasks for additional analysis

        Returns:
            VoyageCalculationResult object with comprehensive voyage metrics
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Basic validation
            if data.average_speed_knots <= 0:
                raise ValueError("Average speed must be greater than zero")
            if data.distance_nm <= 0:
                raise ValueError("Distance must be greater than zero")
            
            # Base travel time calculation in hours
            base_travel_hours = data.distance_nm / data.average_speed_knots
            
            # Get vessel consumption profile if vessel_id is provided
            vessel_profile = None
            vessel_type = "UNKNOWN"
            vessel_deadweight = 0
            
            if db and data.vessel_id:
                vessel_profile = await get_vessel_consumption_profile(db, data.vessel_id)
                
                # Get vessel type for analytics
                vessel_stmt = select(Vessel).where(Vessel.id == data.vessel_id)
                vessel_result = await db.execute(vessel_stmt)
                vessel = vessel_result.scalar_one_or_none()
                
                if vessel:
                    vessel_type = vessel.vessel_type
                    vessel_deadweight = vessel.deadweight_tonnage
            
            # If vessel profile is available, use specific consumption model
            # Otherwise, use provided consumption rate
            if vessel_profile:
                # More accurate consumption calculation based on vessel profile
                base_consumption = self._calculate_consumption_from_profile(
                    vessel_profile, 
                    data.average_speed_knots, 
                    base_travel_hours
                )
            else:
                # Use basic consumption calculation
                base_consumption = round(base_travel_hours * data.fuel_consumption_per_hour, 2)
            
            # Weather impact calculation, if coordinates are provided
            weather_adjusted_hours = base_travel_hours
            weather_impact_factor = 1.0
            weather_alert = None
            extra_consumption_pct = 0.0
            
            if data.route_coordinates and len(data.route_coordinates) > 1:
                # Get weather forecast along the route
                weather_data = None
                
                if background_tasks:
                    # Asynchronously fetch weather
                    try:
                        weather_data = await get_route_weather_forecast(data.route_coordinates)
                    except Exception as we:
                        api_logger.warning(f"Weather data fetch failed: {str(we)}. Using base calculations.")
                
                if weather_data:
                    # Calculate weather impact
                    weather_impact_factor, weather_details = self._calculate_weather_impact(
                        weather_data, 
                        data.route_coordinates,
                        data.average_speed_knots
                    )
                    
                    weather_adjusted_hours = base_travel_hours * weather_impact_factor
                    
                    # Check for severe weather alerts
                    if any(detail.get("sea_state", 0) >= 7 for detail in weather_details):
                        weather_alert = "SEVERE_WEATHER_WARNING"
                        
                    # Calculate extra consumption due to weather
                    extra_consumption_pct = (weather_impact_factor - 1.0) * 100
            
            # Final ETA calculation including weather impact
            eta = data.departure_time + timedelta(hours=weather_adjusted_hours)
            
            # Fuel consumption with weather adjustment
            estimated_consumption = round(base_consumption * weather_impact_factor, 2)
            
            # Check for piracy risk along route
            piracy_risk = "NONE"
            if data.route_coordinates:
                piracy_risk = self._evaluate_piracy_risk(data.route_coordinates)
            
            # Create result object
            result = VoyageCalculationResult(
                calculation_id=request_id,
                vessel_name=data.vessel_name,
                vessel_id=data.vessel_id,
                vessel_type=vessel_type,
                origin_port=data.origin_port,
                destination_port=data.destination_port,
                distance_nm=data.distance_nm,
                departure_time=data.departure_time,
                estimated_arrival_time=eta,
                total_travel_hours=round(weather_adjusted_hours, 2),
                base_travel_hours=round(base_travel_hours, 2),
                weather_impact_hours=round(weather_adjusted_hours - base_travel_hours, 2),
                estimated_fuel_consumption=estimated_consumption,
                base_fuel_consumption=base_consumption,
                extra_consumption_pct=round(extra_consumption_pct, 2),
                average_speed_knots=data.average_speed_knots,
                weather_adjusted_speed=round(data.average_speed_knots / weather_impact_factor, 2),
                weather_impact_factor=round(weather_impact_factor, 3),
                weather_alert=weather_alert,
                piracy_risk=piracy_risk,
                calculation_time=datetime.utcnow()
            )
            
            # Store calculation in database if session provided
            if db and user:
                record = VoyageCalculation(
                    id=request_id,
                    user_id=user.id,
                    vessel_id=data.vessel_id,
                    vessel_name=data.vessel_name,
                    origin_port=data.origin_port,
                    destination_port=data.destination_port,
                    distance_nm=data.distance_nm,
                    departure_time=data.departure_time,
                    estimated_arrival_time=eta,
                    total_travel_hours=round(weather_adjusted_hours, 2),
                    estimated_fuel_consumption=estimated_consumption,
                    average_speed_knots=data.average_speed_knots,
                    weather_impact_factor=round(weather_impact_factor, 3),
                    weather_alert=weather_alert,
                    route_coordinates=data.route_coordinates,
                    calculation_time=datetime.utcnow()
                )
                
                db.add(record)
                await db.commit()
                
                # Invalidate related cache if it exists
                if self.cache_service:
                    await self.cache_service.delete(f"voyage:vessel:{data.vessel_id}:recent")
                    await self.cache_service.delete(f"voyage:user:{user.id}:recent")
            
            # Start background tasks for additional analysis
            if background_tasks and db and user and data.vessel_id:
                background_tasks.add_task(
                    self._analyze_voyage_optimization,
                    db,
                    data,
                    result,
                    user.id
                )
            
            # Log successful calculation
            processing_time = time.time() - start_time
            api_logger.info(
                f"Voyage calculation completed in {processing_time:.2f}s - "
                f"Vessel: {data.vessel_name}, "
                f"Route: {data.origin_port} to {data.destination_port}, "
                f"ETA: {eta.isoformat()}"
            )
            
            return result
            
        except ValueError as ve:
            # Log and re-raise validation errors
            api_logger.warning(f"Validation error in voyage calculation: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
            
        except Exception as e:
            # Log error and raise HTTP exception
            processing_time = time.time() - start_time
            api_logger.error(
                f"Error calculating voyage after {processing_time:.2f}s: {str(e)} - "
                f"Data: {json.dumps(data.dict())}"
            )
            raise HTTPException(status_code=500, detail=f"Error calculating voyage: {str(e)}")
    
    async def optimize_voyage(
        self,
        request: VoyageOptimizationRequest,
        db: AsyncSession,
        user: User
    ) -> Dict:
        """
        Performs multi-variable voyage optimization to find optimal speed,
        route, and departure time based on criteria.
        
        Args:
            request: Optimization parameters and constraints
            db: AsyncSession for data access and storage
            user: User making the request
            
        Returns:
            Dictionary with optimization results and recommendations
        """
        try:
            # Validate optimization request
            if not request.vessel_id:
                raise ValueError("Vessel ID is required for optimization")
                
            if not request.origin_port or not request.destination_port:
                raise ValueError("Origin and destination ports are required")
            
            # Get vessel details
            vessel_stmt = select(Vessel).where(Vessel.id == request.vessel_id)
            vessel_result = await db.execute(vessel_stmt)
            vessel = vessel_result.scalar_one_or_none()
            
            if not vessel:
                raise ValueError(f"Vessel with ID {request.vessel_id} not found")
            
            # Get port details for accurate distance calculation
            # This assumes you have port data with coordinates
            origin_stmt = select(Port).where(Port.code == request.origin_port)
            dest_stmt = select(Port).where(Port.code == request.destination_port)
            
            origin_result = await db.execute(origin_stmt)
            dest_result = await db.execute(dest_stmt)
            
            origin_port = origin_result.scalar_one_or_none()
            dest_port = dest_result.scalar_one_or_none()
            
            if not origin_port or not dest_port:
                raise ValueError("Port information not found")
            
            # Generate route alternatives
            # This is a simplified version - in reality, would use a routing algorithm
            routes = await self._generate_route_alternatives(
                origin_port,
                dest_port,
                request.optimization_criteria
            )
            
            # Generate speed profile alternatives
            speed_options = self._generate_speed_options(
                vessel,
                request.min_speed or 8,
                request.max_speed or 20,
                request.optimization_criteria
            )
            
            # For each route and speed combination, calculate metrics
            optimization_results = []
            
            for route in routes:
                for speed in speed_options:
                    # Create calculation input
                    calc_input = VoyageCalculationInput(
                        vessel_id=request.vessel_id,
                        vessel_name=vessel.name,
                        origin_port=request.origin_port,
                        destination_port=request.destination_port,
                        departure_time=request.earliest_departure or datetime.utcnow(),
                        distance_nm=route["distance"],
                        average_speed_knots=speed["speed"],
                        fuel_consumption_per_hour=speed["consumption"],
                        route_coordinates=route["coordinates"]
                    )
                    
                    # Calculate voyage with this configuration
                    result = await self.calculate_eta(calc_input, db)
                    
                    # Score this combination based on optimization criteria
                    score = self._score_voyage_option(
                        result,
                        request.optimization_criteria,
                        request.latest_arrival
                    )
                    
                    optimization_results.append({
                        "route_name": route["name"],
                        "speed": speed["speed"],
                        "eta": result.estimated_arrival_time,
                        "fuel_consumption": result.estimated_fuel_consumption,
                        "travel_hours": result.total_travel_hours,
                        "score": score,
                        "calculation_id": result.calculation_id
                    })
            
            # Sort by score (highest first)
            optimization_results.sort(key=lambda x: x["score"], reverse=True)
            
            # Get the best option
            best_option = optimization_results[0] if optimization_results else None
            
            # Get the best option for each primary criterion
            time_optimal = next((x for x in optimization_results if x["route_name"] == "Direct" and x["speed"] == max(speed_options, key=lambda s: s["speed"])["speed"]), None)
            fuel_optimal = next((x for x in optimization_results if x["speed"] == min(speed_options, key=lambda s: s["speed"])["speed"]), None)
            balanced = best_option
            
            # Create optimization response
            response = {
                "optimization_id": str(uuid.uuid4()),
                "vessel_id": request.vessel_id,
                "vessel_name": vessel.name,
                "origin_port": request.origin_port,
                "destination_port": request.destination_port,
                "optimization_criteria": request.optimization_criteria,
                "options_evaluated": len(optimization_results),
                "recommended_option": best_option,
                "alternatives": {
                    "time_optimal": time_optimal,
                    "fuel_optimal": fuel_optimal,
                    "balanced": balanced
                },
                "all_options": optimization_results[:5],  # Return top 5 options
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return response
            
        except ValueError as ve:
            api_logger.warning(f"Validation error in voyage optimization: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
            
        except Exception as e:
            api_logger.error(f"Error in voyage optimization: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error optimizing voyage: {str(e)}")
    
    async def get_voyage_history(
        self,
        db: AsyncSession,
        vessel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 20
    ) -> List[VoyageCalculation]:
        """
        Retrieves voyage calculation history with optional filters.
        
        Args:
            db: AsyncSession
            vessel_id: Optional vessel ID filter
            user_id: Optional user ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum records to return
            
        Returns:
            List of VoyageCalculation records
        """
        try:
            # Check cache first
            cache_key = None
            if self.cache_service:
                if vessel_id:
                    cache_key = f"voyage:vessel:{vessel_id}:recent:{limit}"
                elif user_id:
                    cache_key = f"voyage:user:{user_id}:recent:{limit}"
                
                if cache_key:
                    cached_data = await self.cache_service.get(cache_key)
                    if cached_data:
                        return cached_data
            
            # Build query
            query = select(VoyageCalculation)
            
            # Apply filters
            if vessel_id:
                query = query.where(VoyageCalculation.vessel_id == vessel_id)
            if user_id:
                query = query.where(VoyageCalculation.user_id == user_id)
            if start_date:
                query = query.where(VoyageCalculation.calculation_time >= start_date)
            if end_date:
                query = query.where(VoyageCalculation.calculation_time <= end_date)
            
            # Order by calculation time (most recent first) and limit results
            query = query.order_by(desc(VoyageCalculation.calculation_time)).limit(limit)
            
            # Execute query
            result = await db.execute(query)
            records = result.scalars().all()
            
            # Store in cache if applicable
            if cache_key and self.cache_service:
                # Serialize for cache
                serialized = [
                    {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
                    for record in records
                ]
                await self.cache_service.set(cache_key, serialized, expire=300)  # 5 minutes
            
            return records
            
        except Exception as e:
            api_logger.error(f"Error retrieving voyage history: {str(e)}")
            raise HTTPException(status_code=500, detail="Error retrieving voyage history")
    
    async def analyze_vessel_performance(
        self,
        db: AsyncSession,
        vessel_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> VoyagePerformanceMetrics:
        """
        Analyzes historical voyage performance for a specific vessel.
        
        Args:
            db: AsyncSession
            vessel_id: Vessel ID to analyze
            start_date: Optional start date for analysis period
            end_date: Optional end date for analysis period
            
        Returns:
            VoyagePerformanceMetrics with comprehensive analytics
        """
        try:
            # Set default date range if not specified
            if not end_date:
                end_date = datetime.utcnow()
            if not start_date:
                start_date = end_date - timedelta(days=365)  # Last year by default
            
            # Get vessel calculations in date range
            query = select(VoyageCalculation).where(
                VoyageCalculation.vessel_id == vessel_id,
                VoyageCalculation.calculation_time.between(start_date, end_date)
            )
            
            result = await db.execute(query)
            calculations = result.scalars().all()
            
            if not calculations:
                raise HTTPException(status_code=404, detail="No voyage data found for this vessel in the specified period")
            
            # Calculate performance metrics
            total_distance = sum(calc.distance_nm for calc in calculations)
            total_fuel = sum(calc.estimated_fuel_consumption for calc in calculations)
            total_hours = sum(calc.total_travel_hours for calc in calculations)
            
            # Calculate averages
            avg_speed = total_distance / total_hours if total_hours > 0 else 0
            avg_consumption_per_nm = total_fuel / total_distance if total_distance > 0 else 0
            avg_consumption_per_hour = total_fuel / total_hours if total_hours > 0 else 0
            
            # Analyze weather impact
            weather_impacted_voyages = [calc for calc in calculations if calc.weather_impact_factor > 1.05]
            weather_impact_percentage = (len(weather_impacted_voyages) / len(calculations) * 100) if calculations else 0
            
            # Calculate efficiency trend
            # Sort by calculation time
            sorted_calcs = sorted(calculations, key=lambda x: x.calculation_time)
            
            # Calculate efficiency for each voyage (fuel per nautical mile)
            efficiency_trend = []
            for calc in sorted_calcs:
                efficiency = calc.estimated_fuel_consumption / calc.distance_nm if calc.distance_nm > 0 else 0
                efficiency_trend.append({
                    "date": calc.calculation_time.isoformat(),
                    "efficiency": round(efficiency, 4),
                    "route": f"{calc.origin_port} to {calc.destination_port}"
                })
            
            # Determine trend direction
            if len(efficiency_trend) >= 2:
                first_half = efficiency_trend[:len(efficiency_trend)//2]
                second_half = efficiency_trend[len(efficiency_trend)//2:]
                
                first_avg = sum(x["efficiency"] for x in first_half) / len(first_half)
                second_avg = sum(x["efficiency"] for x in second_half) / len(second_half)
                
                if second_avg < first_avg * 0.95:
                    trend_direction = "IMPROVING"
                elif second_avg > first_avg * 1.05:
                    trend_direction = "WORSENING"
                else:
                    trend_direction = "STABLE"
            else:
                trend_direction = "INSUFFICIENT_DATA"
            
            # Create performance metrics response
            performance = VoyagePerformanceMetrics(
                vessel_id=vessel_id,
                analysis_period_start=start_date,
                analysis_period_end=end_date,
                voyages_analyzed=len(calculations),
                total_distance_nm=total_distance,
                total_fuel_consumed=total_fuel,
                total_travel_hours=total_hours,
                average_speed_knots=round(avg_speed, 2),
                average_fuel_per_nm=round(avg_consumption_per_nm, 4),
                average_fuel_per_hour=round(avg_consumption_per_hour, 2),
                weather_impacted_percentage=round(weather_impact_percentage, 2),
                efficiency_trend_direction=trend_direction,
                efficiency_trend_data=efficiency_trend,
                generated_at=datetime.utcnow()
            )
            
            return performance
            
        except HTTPException as he:
            raise he
            
        except Exception as e:
            api_logger.error(f"Error analyzing vessel performance: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error analyzing performance: {str(e)}")
    
    def _calculate_consumption_from_profile(
        self,
        vessel_profile: Dict,
        speed: float,
        hours: float
    ) -> float:
        """
        Calculates fuel consumption based on vessel-specific consumption profile.
        
        Args:
            vessel_profile: Vessel consumption characteristics
            speed: Speed in knots
            hours: Travel duration in hours
            
        Returns:
            Estimated fuel consumption in tons
        """
        # Get consumption curve parameters
        base_speed = vessel_profile.get("base_speed", 10)
        base_consumption = vessel_profile.get("base_consumption", 5)
        consumption_exponent = vessel_profile.get("consumption_exponent", 3.0)
        
        # Apply cubic relationship between speed and consumption
        # This is a simplified version of the admiralty formula
        relative_speed = speed / base_speed
        relative_consumption = relative_speed ** consumption_exponent
        hourly_consumption = base_consumption * relative_consumption
        
        return round(hourly_consumption * hours, 2)
    
    def _calculate_weather_impact(
        self,
        weather_data: List[Dict],
        route_coordinates: List[List[float]],
        vessel_speed: float
    ) -> Tuple[float, List[Dict]]:
        """
        Calculates the impact of weather conditions on voyage speed and duration.
        
        Args:
            weather_data: Weather forecast along the route
            route_coordinates: List of [longitude, latitude] points
            vessel_speed: Base vessel speed in knots
            
        Returns:
            Tuple of (impact_factor, detailed_analysis)
        """
        # This is a simplified weather impact calculation
        # In a real implementation, this would involve complex hydrodynamic modeling
        
        # Calculate route segments
        segments = []
        for i in range(len(route_coordinates) - 1):
            start = route_coordinates[i]
            end = route_coordinates[i + 1]
            
            # Calculate segment length and direction
            # This is a simplified approach - in reality would use geodesic calculations
            length = ((end[0] - start[0])**2 + (end[1] - start[1])**2)**0.5
            
            segments.append({
                "start": start,
                "end": end,
                "length": length
            })
        
        # Total route length for weighting
        total_length = sum(segment["length"] for segment in segments)
        
        # Calculate weather impact for each segment
        segment_impacts = []
        
        for i, segment in enumerate(segments):
            # Find nearest weather data point
            segment_mid = [
                (segment["start"][0] + segment["end"][0]) / 2,
                (segment["start"][1] + segment["end"][1]) / 2
            ]
            
            nearest_weather = min(
                weather_data, 
                key=lambda w: ((w["lon"] - segment_mid[0])**2 + (w["lat"] - segment_mid[1])**2)**0.5
            )
            
            # Get sea state and wind factors
            sea_state = nearest_weather.get("sea_state", 0)
            sea_factor = SEA_STATE_FACTORS.get(sea_state, 1.0)
            
            wind_direction = nearest_weather.get("wind_direction", "beam")
            wind_factor = WIND_DIRECTION_FACTORS.get(wind_direction, 1.0)
            
            # Calculate current impact if available
            current_impact = 1.0
            if "current_speed" in nearest_weather and "current_direction" in nearest_weather:
                current_speed = nearest_weather["current_speed"]
                current_direction = nearest_weather["current_direction"]
                
                if current_direction == "against":
                    effective_speed_reduction = CURRENT_IMPACT["against"](current_speed)
                    current_impact = vessel_speed / (vessel_speed - effective_speed_reduction)
                elif current_direction == "with":
                    effective_speed_increase = CURRENT_IMPACT["with"](current_speed)
                    current_impact = vessel_speed / (vessel_speed + effective_speed_increase)
            
            # Combined impact
            segment_impact = sea_factor * wind_factor * current_impact
            
            # Weight by segment length
            weighted_impact = segment_impact * (segment["length"] / total_length)
            
            segment_impacts.append({
                "segment": i,
                "sea_state": sea_state,
                "wind_direction": wind_direction,
                "impact_factor": segment_impact,
                "weighted_impact": weighted_impact
            })
        
        # Calculate overall impact as weighted average
        overall_impact = sum(impact["weighted_impact"] for impact in segment_impacts)
        
        return overall_impact, segment_impacts
    
    def _evaluate_piracy_risk(self, route_coordinates: List[List[float]]) -> str:
        """
        Evaluates piracy risk along a route by checking for intersection with known risk areas.
        
        Args:
            route_coordinates: List of [longitude, latitude] points
            
        Returns:
            Risk level as string
        """
        # Simplified implementation - checks if any points fall within risk polygons
        for route_point in route_coordinates:
            for region_name, region_data in PIRACY_RISK_REGIONS.items():
                if self._point_in_polygon(route_point, region_data["coordinates"]):
                    return region_data["risk_level"]
        
        return "NONE"
    
    def _point_in_polygon(self, point, polygon) -> bool:
        """
        Determines if a point is inside a polygon using the ray casting algorithm.
        
        Args:
            point: [longitude, latitude]
            polygon: List of [longitude, latitude] points forming a polygon
            
        Returns:
            True if point is in polygon
        """
        # Simplified implementation of point-in-polygon test
        # In reality, would use a proper geospatial library
        
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    async def _generate_route_alternatives(
        self,
        origin_port: Port,
        dest_port: Port,
        optimization_criteria: str
    ) -> List[Dict]:
        """
        Generates alternative routes between ports based on optimization criteria.
        
        Args:
            origin_port: Origin port object
            dest_port: Destination port object
            optimization_criteria: Optimization priority
            
        Returns:
            List of route options with details
        """
        # In a real implementation, this would use a proper routing algorithm
        # This is a simplified version that returns 2-3 alternatives
        
        # Calculate direct route distance
        # Using simplified calculation - would use great circle distance in reality
        direct_distance = ((dest_port.longitude - origin_port.longitude)**2 + 
                          (dest_port.latitude - origin_port.latitude)**2)**0.5 * 60  # Convert degrees to nm
        
        # Direct route (shortest distance)
        direct_route = {
            "name": "Direct",
            "description": "Shortest distance route",
            "distance": direct_distance,
            "coordinates": [
                [origin_port.longitude, origin_port.latitude],
                [dest_port.longitude, dest_port.latitude]
            ]
        }
        
        # Weather-optimized route (slightly longer but potentially better weather)
        # In reality, this would be calculated based on weather forecasts
        weather_optimized = {
            "name": "Weather Optimized",
            "description": "Route adjusted for favorable weather conditions",
            "distance": direct_distance * 1.05,  # 5% longer
            "coordinates": [
                [origin_port.longitude, origin_port.latitude],
                [origin_port.longitude + (dest_port.longitude - origin_port.longitude) * 0.3,
                 origin_port.latitude + (dest_port.latitude - origin_port.latitude) * 0.3 + 0.5],
                [origin_port.longitude + (dest_port.longitude - origin_port.longitude) * 0.7,
                 origin_port.latitude + (dest_port.latitude - origin_port.latitude) * 0.7 + 0.5],
                [dest_port.longitude, dest_port.latitude]
            ]
        }
        
        # Safety route (avoids high-risk areas, potentially longer)
        safety_route = {
            "name": "Safety Route",
            "description": "Route avoiding high-risk areas",
            "distance": direct_distance * 1.12,  # 12% longer
            "coordinates": [
                [origin_port.longitude, origin_port.latitude],
                [origin_port.longitude + (dest_port.longitude - origin_port.longitude) * 0.25,
                 origin_port.latitude + (dest_port.latitude - origin_port.latitude) * 0.25 - 1.0],
                [origin_port.longitude + (dest_port.longitude - origin_port.longitude) * 0.75,
                 origin_port.latitude + (dest_port.latitude - origin_port.latitude) * 0.75 - 1.0],
                [dest_port.longitude, dest_port.latitude]
            ]
        }
        
        # Return appropriate routes based on optimization criteria
        if optimization_criteria == "FUEL_ECONOMY":
            # For fuel economy, prefer weather-optimized routes that may allow for more efficient sailing
            return [weather_optimized, direct_route, safety_route]
        elif optimization_criteria == "TIME":
            # For time optimization, prefer the direct route
            return [direct_route, weather_optimized, safety_route]
        elif optimization_criteria == "SAFETY":
            # For safety, prioritize the safer route
            return [safety_route, weather_optimized, direct_route]
        else:
            # Balanced approach
            return [direct_route, weather_optimized, safety_route]
    
    def _generate_speed_options(
        self,
        vessel: Vessel,
        min_speed: float,
        max_speed: float,
        optimization_criteria: str
    ) -> List[Dict]:
        """
        Generates speed options for optimization based on vessel characteristics and criteria.
        
        Args:
            vessel: Vessel object with specifications
            min_speed: Minimum acceptable speed
            max_speed: Maximum acceptable speed
            optimization_criteria: Optimization priority
            
        Returns:
            List of speed options with details
        """
        # Get vessel's design speed and consumption profile
        design_speed = vessel.design_speed or 14.0
        design_consumption = vessel.design_consumption or 30.0
        
        # Generate speed options
        speed_options = []
        
        # Eco speed (lowest fuel consumption)
        eco_speed = max(min_speed, design_speed * 0.8)
        eco_consumption = design_consumption * (eco_speed / design_speed) ** 3
        
        speed_options.append({
            "name": "Eco Speed",
            "speed": eco_speed,
            "consumption": eco_consumption,
            "description": "Optimized for fuel economy"
        })
        
        # Standard speed
        standard_speed = design_speed
        standard_consumption = design_consumption
        
        speed_options.append({
            "name": "Standard Speed",
            "speed": standard_speed,
            "consumption": standard_consumption,
            "description": "Vessel's design speed"
        })
        
        # Fast speed
        fast_speed = min(max_speed, design_speed * 1.1)
        fast_consumption = design_consumption * (fast_speed / design_speed) ** 3
        
        speed_options.append({
            "name": "Fast Speed",
            "speed": fast_speed,
            "consumption": fast_consumption,
            "description": "Higher speed for shorter transit time"
        })
        
        # Maximum speed
        max_feasible_speed = min(max_speed, design_speed * 1.2)
        max_consumption = design_consumption * (max_feasible_speed / design_speed) ** 3
        
        speed_options.append({
            "name": "Maximum Speed",
            "speed": max_feasible_speed,
            "consumption": max_consumption,
            "description": "Maximum recommended speed"
        })
        
        return speed_options
    
    def _score_voyage_option(
        self,
        result: VoyageCalculationResult,
        optimization_criteria: str,
        latest_arrival: Optional[datetime] = None
    ) -> float:
        """
        Scores a voyage option based on optimization criteria.
        
        Args:
            result: Calculation result to score
            optimization_criteria: Optimization priority
            latest_arrival: Optional latest acceptable arrival time
            
        Returns:
            Numerical score (higher is better)
        """
        # Base score starts at 100
        score = 100.0
        
        # Check if arrival is within deadline
        if latest_arrival and result.estimated_arrival_time > latest_arrival:
            # Severe penalty for missing deadline
            hours_late = (result.estimated_arrival_time - latest_arrival).total_seconds() / 3600
            score -= min(50, hours_late * 5)  # Up to 50 point penalty
        
        # Apply criteria-specific scoring
        if optimization_criteria == "FUEL_ECONOMY":
            # Reward fuel efficiency
            fuel_per_nm = result.estimated_fuel_consumption / result.distance_nm
            score += (1.0 / fuel_per_nm) * 10  # Higher score for lower consumption per nm
            
        elif optimization_criteria == "TIME":
            # Reward faster voyages
            speed_factor = result.average_speed_knots / 10.0  # Normalize to typical speed
            score += speed_factor * 30  # Up to 30 extra points for speed
            
        elif optimization_criteria == "SAFETY":
            # Reward routes with lower weather impact and no piracy risk
            if result.weather_impact_factor > 1.2:
                score -= (result.weather_impact_factor - 1.0) * 50  # Penalty for bad weather
                
            if result.piracy_risk != "NONE":
                score -= 40  # Significant penalty for piracy risk
                
        else:  # BALANCED
            # Balanced approach
            fuel_per_nm = result.estimated_fuel_consumption / result.distance_nm
            speed_factor = result.average_speed_knots / 10.0
            
            score += (1.0 / fuel_per_nm) * 5  # Some reward for efficiency
            score += speed_factor * 15       # Some reward for speed
            
            # Small penalty for weather and risks
            if result.weather_impact_factor > 1.1:
                score -= (result.weather_impact_factor - 1.0) * 20
                
            if result.piracy_risk != "NONE":
                score -= 20
        
        return max(0, score)  # Ensure score doesn't go negative
    
    async def _analyze_voyage_optimization(
        self,
        db: AsyncSession,
        input_data: VoyageCalculationInput,
        result: VoyageCalculationResult,
        user_id: int
    ) -> None:
        """
        Background task to analyze voyage data and generate optimization insights.
        
        Args:
            db: AsyncSession
            input_data: Original calculation input
            result: Calculation result
            user_id: User ID for attribution
        """
        try:
            # Get vessel profile
            vessel_profile = None
            if input_data.vessel_id:
                vessel_profile = await get_vessel_consumption_profile(db, input_data.vessel_id)
            
            if not vessel_profile:
                return  # Can't optimize without vessel profile
            
            # Calculate different speed scenarios
            speeds_to_try = [
                input_data.average_speed_knots * 0.9,  # 10% slower
                input_data.average_speed_knots * 0.95, # 5% slower
                input_data.average_speed_knots,        # Current speed
                input_data.average_speed_knots * 1.05, # 5% faster
                input_data.average_speed_knots * 1.1   # 10% faster
            ]
            
            # Calculate consumption for each speed
            scenarios = []
            for speed in speeds_to_try:
                travel_hours = input_data.distance_nm / speed
                consumption = self._calculate_consumption_from_profile(
                    vessel_profile, 
                    speed, 
                    travel_hours
                )
                
                scenarios.append({
                    "speed": round(speed, 2),
                    "travel_hours": round(travel_hours, 2),
                    "consumption": round(consumption, 2),
                    "arrival": (input_data.departure_time + timedelta(hours=travel_hours)).isoformat()
                })
            
            # Find optimal speed for fuel efficiency
            scenarios.sort(key=lambda x: x["consumption"])
            most_efficient = scenarios[0]
            
            # Find fastest scenario
            scenarios.sort(key=lambda x: x["travel_hours"])
            fastest = scenarios[0]
            
            # Store optimization results
            # In a real implementation, would store in a database table
            
            api_logger.info(
                f"Voyage optimization analysis completed for vessel {input_data.vessel_id}, "
                f"route {input_data.origin_port} to {input_data.destination_port}. "
                f"Most efficient speed: {most_efficient['speed']} knots "
                f"({round((most_efficient['consumption'] / result.estimated_fuel_consumption - 1) * 100, 2)}% fuel savings)"
            )
            
        except Exception as e:
            api_logger.error(f"Error in voyage optimization analysis: {str(e)}")


# Create calculator instance
voyage_calculator = VoyageCalculator()

# Main wrapper function for ETA calculation
async def calculate_eta(
    data: VoyageCalculationInput,
    db: Optional[AsyncSession] = None,
    user: Optional[User] = None,
    background_tasks: Optional[BackgroundTasks] = None
) -> VoyageCalculationResult:
    """
    Facade function to calculate voyage ETA with weather integration.
    
    Args:
        data: Voyage information (ports, speed, consumption, distance)
        db: Optional AsyncSession for storing results
        user: Optional User for record attribution
        background_tasks: Optional background tasks for additional analysis
        
    Returns:
        VoyageCalculationResult with comprehensive voyage metrics
    """
    # Get cache service if available
    try:
        cache_service = await get_voyage_cache()
    except:
        cache_service = None
    
    calculator = VoyageCalculator(cache_service)
    return await calculator.calculate_eta(data, db, user, background_tasks)

# Wrapper function for voyage optimization
async def optimize_voyage(
    request: VoyageOptimizationRequest,
    db: AsyncSession,
    user: User
) -> Dict:
    """
    Facade function for voyage optimization.
    
    Args:
        request: Optimization parameters and constraints
        db: AsyncSession for data access and storage
        user: User making the request
        
    Returns:
        Dictionary with optimization results and recommendations
    """
    # Get cache service if available
    try:
        cache_service = await get_voyage_cache()
    except:
        cache_service = None
    
    calculator = VoyageCalculator(cache_service)
    return await calculator.optimize_voyage(request, db, user)

# Wrapper function for voyage history retrieval
async def get_voyage_history(
    db: AsyncSession,
    vessel_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20
) -> List:
    """
    Facade function to retrieve voyage calculation history.
    
    Args:
        db: AsyncSession
        vessel_id: Optional vessel ID filter
        user_id: Optional user ID filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum records to return
        
    Returns:
        List of VoyageCalculation records
    """
    # Get cache service if available
    try:
        cache_service = await get_voyage_cache()
    except:
        cache_service = None
    
    calculator = VoyageCalculator(cache_service)
    return await calculator.get_voyage_history(
        db, vessel_id, user_id, start_date, end_date, limit
    )

# Wrapper function for performance analysis
async def analyze_vessel_performance(
    db: AsyncSession,
    vessel_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> VoyagePerformanceMetrics:
    """
    Facade function to analyze vessel performance.
    
    Args:
        db: AsyncSession
        vessel_id: Vessel ID to analyze
        start_date: Optional start date for analysis period
        end_date: Optional end date for analysis period
        
    Returns:
        VoyagePerformanceMetrics with performance analytics
    """
    calculator = VoyageCalculator()
    return await calculator.analyze_vessel_performance(
        db, vessel_id, start_date, end_date
    )