# Path: backend/app/utils/weather.py

import os
import json
import time
import asyncio
import hmac
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Dict, List, Optional, Union, Tuple, Any, Callable
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, validator, root_validator
from geojson import Feature, Point, FeatureCollection

from app.core.config import settings
from app.core.logging import api_logger, weather_logger
from app.core.cache import RedisCache
from app.utils.geolocation import haversine_distance_km, validate_coordinates
from app.services.notification_service import send_weather_alert
from app.models.weather import WeatherRecord, WeatherAlert, ForecastRecord
from app.exceptions.api_exceptions import (
    WeatherApiError,
    ExternalServiceUnavailableError,
    ConfigurationError,
    RateLimitExceededError
)

# Configuration constants
WEATHER_PROVIDERS = {
    "openweathermap": {
        "current": "https://api.openweathermap.org/data/2.5/weather",
        "forecast": "https://api.openweathermap.org/data/2.5/forecast",
        "onecall": "https://api.openweathermap.org/data/3.0/onecall",
        "marine": "https://api.openweathermap.org/data/2.5/forecast/marine",
        "auth_type": "api_key",
        "rate_limit": 60,  # requests per minute
        "timeout": 10.0,  # seconds
        "retry_attempts": 3
    },
    "weatherapi": {
        "current": "https://api.weatherapi.com/v1/current.json",
        "forecast": "https://api.weatherapi.com/v1/forecast.json",
        "marine": "https://api.weatherapi.com/v1/marine.json",
        "auth_type": "api_key",
        "rate_limit": 100,  # requests per minute
        "timeout": 8.0,
        "retry_attempts": 3
    },
    "tomorrow": {
        "current": "https://api.tomorrow.io/v4/weather/realtime",
        "forecast": "https://api.tomorrow.io/v4/weather/forecast",
        "auth_type": "api_key",
        "rate_limit": 50,
        "timeout": 15.0,
        "retry_attempts": 2
    }
}

# Default provider configuration
DEFAULT_PROVIDER = os.getenv("WEATHER_DEFAULT_PROVIDER", "openweathermap")
DEFAULT_UNITS = os.getenv("WEATHER_DEFAULT_UNITS", "metric")
CACHE_ENABLED = settings.WEATHER_CACHE_ENABLED
CACHE_TTL = settings.WEATHER_CACHE_TTL
WEATHER_ALERT_ENABLED = settings.WEATHER_ALERT_ENABLED


class WeatherUnits(str, Enum):
    """Weather measurement units."""
    METRIC = "metric"
    IMPERIAL = "imperial"
    STANDARD = "standard"  # Kelvin for temperature


class ForecastType(str, Enum):
    """Types of weather forecasts."""
    HOURLY = "hourly"
    DAILY = "daily"
    MARINE = "marine"
    AVIATION = "aviation"


class WeatherSource(str, Enum):
    """Weather data sources."""
    OPENWEATHERMAP = "openweathermap"
    WEATHERAPI = "weatherapi"
    TOMORROW = "tomorrow"
    FALLBACK = "fallback"  # Combined from multiple sources
    CACHE = "cache"


class WeatherSeverity(str, Enum):
    """Weather alert severity levels."""
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class WeatherParameters(BaseModel):
    """Parameters for weather API requests."""
    lat: float
    lon: float
    units: WeatherUnits = WeatherUnits.METRIC
    language: str = "en"
    include_alerts: bool = True
    exclude: Optional[List[str]] = None
    provider: WeatherSource = WeatherSource(DEFAULT_PROVIDER)

    @validator('lat')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return round(v, 6)

    @validator('lon')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return round(v, 6)


class ForecastParameters(WeatherParameters):
    """Parameters for forecast API requests."""
    days: int = 5
    hours: int = 24
    forecast_type: ForecastType = ForecastType.DAILY
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @validator('days')
    def validate_days(cls, v):
        if not 1 <= v <= 16:
            raise ValueError("Forecast days must be between 1 and 16")
        return v

    @validator('hours')
    def validate_hours(cls, v):
        if not 1 <= v <= 120:
            raise ValueError("Forecast hours must be between 1 and 120")
        return v

    @root_validator
    def check_dates(cls, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise ValueError("start_date must be before end_date")
            
            # Limit to 16 days max
            if end_date - start_date > timedelta(days=16):
                raise ValueError("Date range cannot exceed 16 days")
        
        return values


class MarineParameters(ForecastParameters):
    """Parameters for marine weather forecasts."""
    sea_height: bool = True
    swell_data: bool = True
    tide_data: bool = False
    current_data: bool = False


class WeatherResponse(BaseModel):
    """Standardized weather response model."""
    location: Dict[str, Any]
    current: Dict[str, Any]
    units: WeatherUnits
    source: WeatherSource
    alerts: Optional[List[Dict[str, Any]]] = None
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    provider_response_time_ms: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class ForecastResponse(BaseModel):
    """Standardized forecast response model."""
    location: Dict[str, Any]
    forecast: Dict[str, Any]
    units: WeatherUnits
    source: WeatherSource
    forecast_type: ForecastType
    alerts: Optional[List[Dict[str, Any]]] = None
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    provider_response_time_ms: Optional[int] = None
    raw_data: Optional[Dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class WeatherClient:
    """
    Enterprise-grade weather data client with multiple provider support,
    caching, failover, and standardized responses.
    """
    
    def __init__(
        self,
        api_keys: Optional[Dict[str, str]] = None,
        default_provider: str = DEFAULT_PROVIDER,
        cache: Optional[RedisCache] = None,
        timeout: float = 30.0,
        use_mock: bool = False
    ):
        """
        Initialize the weather client.
        
        Args:
            api_keys: Dictionary of provider names to API keys
            default_provider: Default weather provider
            cache: Optional Redis cache instance
            timeout: Default timeout for HTTP requests
            use_mock: Whether to use mock data for testing
        """
        self.api_keys = api_keys or {}
        self.default_provider = default_provider
        self.cache = cache
        self.timeout = timeout
        self.use_mock = use_mock
        self.rate_limiters = {}
        
        # Initialize rate limiters
        for provider, config in WEATHER_PROVIDERS.items():
            self.rate_limiters[provider] = {
                "limit": config["rate_limit"],
                "window": 60,  # 1 minute window
                "requests": [],
                "last_reset": time.time()
            }
        
        # Load API keys from environment if not provided
        if not self.api_keys:
            self._load_api_keys_from_env()
        
        # Validate configuration
        self._validate_configuration()
    
    async def get_current_weather(
        self,
        params: Union[WeatherParameters, Dict[str, Any]],
        store_in_db: bool = False,
        db_session = None
    ) -> WeatherResponse:
        """
        Get current weather conditions for a location.
        
        Args:
            params: Weather parameters
            store_in_db: Whether to store results in database
            db_session: Optional database session
            
        Returns:
            Standardized weather response
        """
        if isinstance(params, dict):
            params = WeatherParameters(**params)
        
        # Try to get from cache first
        if CACHE_ENABLED and self.cache:
            cache_key = self._get_cache_key("current", params)
            cached_data = await self.cache.get(cache_key)
            
            if cached_data:
                weather_data = json.loads(cached_data)
                
                # Add cache hit information
                weather_data["cache_hit"] = True
                
                # Update requested_at
                weather_data["requested_at"] = datetime.utcnow().isoformat()
                
                weather_logger.info(
                    f"Cache hit for weather data at [{params.lat}, {params.lon}]"
                )
                
                return WeatherResponse(**weather_data)
        
        # Request from provider
        provider = params.provider.value
        start_time = time.time()
        
        try:
            # Check rate limits
            if not self._check_rate_limit(provider):
                # Try fallback provider if rate limited
                if provider != self.default_provider:
                    weather_logger.warning(
                        f"Rate limit exceeded for {provider}, falling back to {self.default_provider}"
                    )
                    params.provider = WeatherSource(self.default_provider)
                    return await self.get_current_weather(params, store_in_db, db_session)
                else:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for provider {provider}"
                    )
            
            # Make request to weather provider
            weather_data = await self._fetch_from_provider(
                provider, "current", params
            )
            
            # Record the request for rate limiting
            self._record_request(provider)
            
            # Process response into standardized format
            standardized_data = self._standardize_current_weather(
                weather_data, params, provider
            )
            
            # Add performance metrics
            processing_time = int((time.time() - start_time) * 1000)
            standardized_data["provider_response_time_ms"] = processing_time
            
            # Store raw data for debugging if needed
            if settings.WEATHER_INCLUDE_RAW_DATA:
                standardized_data["raw_data"] = weather_data
            
            response = WeatherResponse(**standardized_data)
            
            # Store in cache if enabled
            if CACHE_ENABLED and self.cache:
                # Don't store cache_hit in the cached data
                cache_data = response.dict()
                cache_data.pop("cache_hit", None)
                
                await self.cache.set(
                    cache_key,
                    json.dumps(cache_data),
                    expire=CACHE_TTL
                )
            
            # Store in database if requested
            if store_in_db and db_session:
                await self._store_weather_in_db(response, db_session)
            
            # Check for severe weather alerts and process if necessary
            if WEATHER_ALERT_ENABLED and response.alerts:
                await self._process_weather_alerts(response)
            
            weather_logger.info(
                f"Successfully fetched weather for [{params.lat}, {params.lon}] "
                f"from {provider} in {processing_time}ms"
            )
            
            return response
            
        except RateLimitExceededError:
            # If this is the default provider, try an alternative
            if provider == self.default_provider:
                alternate_provider = self._get_alternate_provider()
                if alternate_provider:
                    weather_logger.warning(
                        f"Trying alternate provider {alternate_provider} due to rate limit"
                    )
                    params.provider = WeatherSource(alternate_provider)
                    return await self.get_current_weather(params, store_in_db, db_session)
            
            # Re-raise if no alternatives or already using alternatives
            raise
            
        except httpx.HTTPError as e:
            weather_logger.error(
                f"HTTP error fetching weather for [{params.lat}, {params.lon}] "
                f"from {provider}: {str(e)}"
            )
            
            # Try fallback if not already using it
            if provider != self.default_provider:
                weather_logger.warning(
                    f"Falling back to {self.default_provider} after HTTP error"
                )
                params.provider = WeatherSource(self.default_provider)
                return await self.get_current_weather(params, store_in_db, db_session)
            
            raise ExternalServiceUnavailableError(
                f"Weather provider {provider} unavailable: {str(e)}"
            )
            
        except Exception as e:
            weather_logger.error(
                f"Unexpected error fetching weather for [{params.lat}, {params.lon}]: {str(e)}"
            )
            raise WeatherApiError(f"Error fetching weather data: {str(e)}")
    
    async def get_weather_forecast(
        self,
        params: Union[ForecastParameters, Dict[str, Any]],
        store_in_db: bool = False,
        db_session = None
    ) -> ForecastResponse:
        """
        Get weather forecast for a location.
        
        Args:
            params: Forecast parameters
            store_in_db: Whether to store results in database
            db_session: Optional database session
            
        Returns:
            Standardized forecast response
        """
        if isinstance(params, dict):
            params = ForecastParameters(**params)
        
        # Try to get from cache first
        if CACHE_ENABLED and self.cache:
            cache_key = self._get_cache_key("forecast", params)
            cached_data = await self.cache.get(cache_key)
            
            if cached_data:
                forecast_data = json.loads(cached_data)
                
                # Add cache hit information
                forecast_data["cache_hit"] = True
                
                # Update requested_at
                forecast_data["requested_at"] = datetime.utcnow().isoformat()
                
                weather_logger.info(
                    f"Cache hit for forecast data at [{params.lat}, {params.lon}]"
                )
                
                return ForecastResponse(**forecast_data)
        
        # Request from provider
        provider = params.provider.value
        start_time = time.time()
        
        try:
            # Check rate limits
            if not self._check_rate_limit(provider):
                # Try fallback provider if rate limited
                if provider != self.default_provider:
                    weather_logger.warning(
                        f"Rate limit exceeded for {provider}, falling back to {self.default_provider}"
                    )
                    params.provider = WeatherSource(self.default_provider)
                    return await self.get_weather_forecast(params, store_in_db, db_session)
                else:
                    raise RateLimitExceededError(
                        f"Rate limit exceeded for provider {provider}"
                    )
            
            # Determine which endpoint to use based on forecast type
            endpoint = "forecast"
            if params.forecast_type == ForecastType.MARINE:
                endpoint = "marine"
            
            # Make request to weather provider
            forecast_data = await self._fetch_from_provider(
                provider, endpoint, params
            )
            
            # Record the request for rate limiting
            self._record_request(provider)
            
            # Process response into standardized format
            standardized_data = self._standardize_forecast(
                forecast_data, params, provider
            )
            
            # Add performance metrics
            processing_time = int((time.time() - start_time) * 1000)
            standardized_data["provider_response_time_ms"] = processing_time
            
            # Store raw data for debugging if needed
            if settings.WEATHER_INCLUDE_RAW_DATA:
                standardized_data["raw_data"] = forecast_data
            
            response = ForecastResponse(**standardized_data)
            
            # Store in cache if enabled
            if CACHE_ENABLED and self.cache:
                # Don't store cache_hit in the cached data
                cache_data = response.dict()
                cache_data.pop("cache_hit", None)
                
                await self.cache.set(
                    cache_key,
                    json.dumps(cache_data),
                    expire=CACHE_TTL
                )
            
            # Store in database if requested
            if store_in_db and db_session:
                await self._store_forecast_in_db(response, db_session)
            
            weather_logger.info(
                f"Successfully fetched forecast for [{params.lat}, {params.lon}] "
                f"from {provider} in {processing_time}ms"
            )
            
            return response
            
        except RateLimitExceededError:
            # If this is the default provider, try an alternative
            if provider == self.default_provider:
                alternate_provider = self._get_alternate_provider()
                if alternate_provider:
                    weather_logger.warning(
                        f"Trying alternate provider {alternate_provider} due to rate limit"
                    )
                    params.provider = WeatherSource(alternate_provider)
                    return await self.get_weather_forecast(params, store_in_db, db_session)
            
            # Re-raise if no alternatives or already using alternatives
            raise
            
        except httpx.HTTPError as e:
            weather_logger.error(
                f"HTTP error fetching forecast for [{params.lat}, {params.lon}] "
                f"from {provider}: {str(e)}"
            )
            
            # Try fallback if not already using it
            if provider != self.default_provider:
                weather_logger.warning(
                    f"Falling back to {self.default_provider} after HTTP error"
                )
                params.provider = WeatherSource(self.default_provider)
                return await self.get_weather_forecast(params, store_in_db, db_session)
            
            raise ExternalServiceUnavailableError(
                f"Weather provider {provider} unavailable: {str(e)}"
            )
            
        except Exception as e:
            weather_logger.error(
                f"Unexpected error fetching forecast for [{params.lat}, {params.lon}]: {str(e)}"
            )
            raise WeatherApiError(f"Error fetching forecast data: {str(e)}")
    
    async def get_marine_forecast(
        self,
        params: Union[MarineParameters, Dict[str, Any]],
        store_in_db: bool = False,
        db_session = None
    ) -> ForecastResponse:
        """
        Get marine weather forecast for a location.
        
        Args:
            params: Marine forecast parameters
            store_in_db: Whether to store results in database
            db_session: Optional database session
            
        Returns:
            Standardized marine forecast response
        """
        if isinstance(params, dict):
            params = MarineParameters(**params)
        
        # Force marine forecast type
        params.forecast_type = ForecastType.MARINE
        
        # Use marine-specific endpoint
        return await self.get_weather_forecast(params, store_in_db, db_session)
    
    async def get_weather_for_route(
        self,
        route_points: List[Tuple[float, float]],
        params: Optional[WeatherParameters] = None,
        max_distance_km: float = 50.0
    ) -> List[WeatherResponse]:
        """
        Get weather data for multiple points along a route.
        
        Args:
            route_points: List of (lat, lon) tuples defining the route
            params: Base weather parameters to use
            max_distance_km: Maximum distance between weather points
            
        Returns:
            List of weather responses for points along the route
        """
        if not route_points or len(route_points) < 2:
            raise ValueError("Route must have at least two points")
        
        base_params = params or WeatherParameters(
            lat=route_points[0][0],
            lon=route_points[0][1]
        )
        
        # Determine sampling points along the route
        sample_points = self._sample_route_points(route_points, max_distance_km)
        
        # Fetch weather for each sample point
        results = []
        tasks = []
        
        for lat, lon in sample_points:
            point_params = base_params.copy()
            point_params.lat = lat
            point_params.lon = lon
            
            tasks.append(self.get_current_weather(point_params))
        
        # Execute requests concurrently
        results = await asyncio.gather(*tasks)
        
        return results
    
    async def get_consolidated_route_weather(
        self,
        route_points: List[Tuple[float, float]],
        params: Optional[WeatherParameters] = None,
        max_distance_km: float = 50.0
    ) -> Dict[str, Any]:
        """
        Get consolidated weather information for a route.
        
        Args:
            route_points: List of (lat, lon) tuples defining the route
            params: Base weather parameters to use
            max_distance_km: Maximum distance between weather points
            
        Returns:
            Consolidated weather information for the route
        """
        # Get individual weather data points
        weather_points = await self.get_weather_for_route(
            route_points, params, max_distance_km
        )
        
        # Extract and consolidate data
        consolidated = {
            "route_summary": {
                "start_point": route_points[0],
                "end_point": route_points[-1],
                "distance_km": self._calculate_route_distance(route_points),
                "weather_samples": len(weather_points),
                "generated_at": datetime.utcnow().isoformat()
            },
            "weather_conditions": {
                "temperature_range": {
                    "min": min(w.current.get("temp", 0) for w in weather_points),
                    "max": max(w.current.get("temp", 0) for w in weather_points),
                    "avg": sum(w.current.get("temp", 0) for w in weather_points) / len(weather_points)
                },
                "wind_speed_range": {
                    "min": min(w.current.get("wind_speed", 0) for w in weather_points),
                    "max": max(w.current.get("wind_speed", 0) for w in weather_points),
                    "avg": sum(w.current.get("wind_speed", 0) for w in weather_points) / len(weather_points)
                },
                "precipitation": any(
                    w.current.get("rain", {}).get("1h", 0) > 0 or 
                    w.current.get("snow", {}).get("1h", 0) > 0 
                    for w in weather_points
                ),
                "conditions": self._get_dominant_condition(weather_points)
            },
            "alerts": self._consolidate_alerts(weather_points),
            "points": [
                {
                    "location": {
                        "lat": w.location.get("lat"),
                        "lon": w.location.get("lon"),
                        "name": w.location.get("name", "Route Point")
                    },
                    "conditions": {
                        "temp": w.current.get("temp"),
                        "wind_speed": w.current.get("wind_speed"),
                        "wind_direction": w.current.get("wind_deg"),
                        "weather": w.current.get("weather", [{}])[0].get("main")
                    }
                }
                for w in weather_points
            ]
        }
        
        return consolidated
    
    async def check_severe_weather(
        self,
        params: WeatherParameters,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Check for severe weather conditions and alerts.
        
        Args:
            params: Weather parameters
            background_tasks: Optional background tasks
            
        Returns:
            Severe weather assessment and alerts
        """
        weather = await self.get_current_weather(params)
        
        # Initialize response
        assessment = {
            "has_severe_conditions": False,
            "alerts": [],
            "severe_conditions": [],
            "location": weather.location,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Check for severe weather alerts
        if weather.alerts:
            assessment["has_severe_conditions"] = True
            assessment["alerts"] = weather.alerts
        
        # Check for extreme weather conditions
        conditions = []
        
        # Check wind speed (above 50 km/h is considered severe)
        if weather.current.get("wind_speed", 0) > 50:
            conditions.append({
                "type": "high_wind",
                "value": weather.current.get("wind_speed"),
                "threshold": 50,
                "units": "km/h",
                "severity": WeatherSeverity.MODERATE
            })
        
        # Check for heavy precipitation
        if weather.current.get("rain", {}).get("1h", 0) > 10:
            conditions.append({
                "type": "heavy_rain",
                "value": weather.current.get("rain", {}).get("1h"),
                "threshold": 10,
                "units": "mm",
                "severity": WeatherSeverity.MODERATE
            })
        
        # Check for extreme temperatures
        if weather.current.get("temp", 0) > 40:
            conditions.append({
                "type": "extreme_heat",
                "value": weather.current.get("temp"),
                "threshold": 40,
                "units": "°C",
                "severity": WeatherSeverity.MODERATE
            })
        
        if weather.current.get("temp", 0) < -20:
            conditions.append({
                "type": "extreme_cold",
                "value": weather.current.get("temp"),
                "threshold": -20,
                "units": "°C",
                "severity": WeatherSeverity.MODERATE
            })
        
        # Update assessment
        if conditions:
            assessment["has_severe_conditions"] = True
            assessment["severe_conditions"] = conditions
        
        # Process alerts in background task if provided
        if background_tasks and assessment["has_severe_conditions"]:
            background_tasks.add_task(
                self._process_severe_weather_assessment,
                assessment,
                weather.location
            )
        
        return assessment
    
    async def _fetch_from_provider(
        self,
        provider: str,
        endpoint: str,
        params: BaseModel
    ) -> Dict[str, Any]:
        """
        Fetch data from a specific weather provider.
        
        Args:
            provider: Provider name
            endpoint: API endpoint type
            params: Request parameters
            
        Returns:
            Weather data
        """
        # If using mock data for testing
        if self.use_mock:
            return self._get_mock_data(provider, endpoint, params)
        
        # Get provider configuration
        if provider not in WEATHER_PROVIDERS:
            raise ValueError(f"Unsupported weather provider: {provider}")
        
        provider_config = WEATHER_PROVIDERS[provider]
        api_key = self.api_keys.get(provider)
        
        if not api_key:
            raise ConfigurationError(f"API key not configured for provider: {provider}")
        
        # Build URL
        base_url = provider_config.get(endpoint)
        if not base_url:
            raise ValueError(f"Endpoint {endpoint} not supported by provider {provider}")
        
        # Prepare request parameters
        request_params = self._prepare_request_params(provider, endpoint, params)
        
        # Add authentication
        auth_type = provider_config.get("auth_type", "api_key")
        if auth_type == "api_key":
            request_params["appid" if provider == "openweathermap" else "key"] = api_key
        
        # Prepare timeout and retry config
        timeout = provider_config.get("timeout", self.timeout)
        retry_attempts = provider_config.get("retry_attempts", 1)
        
        # Make the request with retries
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(retry_attempts):
                try:
                    response = await client.get(base_url, params=request_params)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as e:
                    # Check for rate limiting
                    if e.response.status_code == 429:
                        raise RateLimitExceededError(
                            f"Rate limit exceeded for provider {provider}"
                        )
                    
                    # If last attempt, re-raise
                    if attempt == retry_attempts - 1:
                        raise
                    
                    # Otherwise wait and retry
                    retry_delay = 2 ** attempt  # Exponential backoff
                    await asyncio.sleep(retry_delay)
                except httpx.RequestError as e:
                    # If last attempt, re-raise
                    if attempt == retry_attempts - 1:
                        raise
                    
                    # Otherwise wait and retry
                    retry_delay = 2 ** attempt
                    await asyncio.sleep(retry_delay)
    
    def _prepare_request_params(
        self,
        provider: str,
        endpoint: str,
        params: BaseModel
    ) -> Dict[str, Any]:
        """
        Prepare provider-specific request parameters.
        
        Args:
            provider: Provider name
            endpoint: API endpoint type
            params: Request parameters
            
        Returns:
            Dictionary of request parameters
        """
        if provider == "openweathermap":
            request_params = {
                "lat": params.lat,
                "lon": params.lon,
                "units": params.units.value,
                "lang": params.language
            }
            
            # Add forecast-specific parameters
            if isinstance(params, ForecastParameters):
                if endpoint == "forecast":
                    # OpenWeatherMap's free forecast is 5 days / 3 hours
                    pass  # Use defaults
                elif endpoint == "onecall":
                    # OneCall API specific parameters
                    if params.exclude:
                        request_params["exclude"] = ",".join(params.exclude)
            
            # Marine-specific parameters
            if isinstance(params, MarineParameters) and endpoint == "marine":
                if params.sea_height:
                    request_params["sea"] = "yes"
                
        elif provider == "weatherapi":
            request_params = {
                "q": f"{params.lat},{params.lon}",
                "lang": params.language
            }
            
            # Add forecast-specific parameters
            if isinstance(params, ForecastParameters):
                if endpoint == "forecast":
                    request_params["days"] = params.days
                    if params.forecast_type == ForecastType.HOURLY:
                        request_params["hour"] = "1"  # 1-hour intervals
            
            # Marine-specific parameters
            if isinstance(params, MarineParameters) and endpoint == "marine":
                request_params["tide"] = "yes" if params.tide_data else "no"
                
        elif provider == "tomorrow":
            request_params = {
                "location": f"{params.lat},{params.lon}",
                "units": params.units.value
            }
            
            # Add forecast-specific parameters
            if isinstance(params, ForecastParameters) and endpoint == "forecast":
                if params.forecast_type == ForecastType.HOURLY:
                    request_params["timesteps"] = "1h"
                else:
                    request_params["timesteps"] = "1d"
        
        return request_params
    
    def _standardize_current_weather(
        self,
        weather_data: Dict[str, Any],
        params: WeatherParameters,
        provider: str
    ) -> Dict[str, Any]:
        """
        Convert provider-specific weather data to standardized format.
        
        Args:
            weather_data: Provider's weather data
            params: Request parameters
            provider: Provider name
            
        Returns:
            Standardized weather data
        """
        # Extract basic location information
        location = {}
        current = {}
        alerts = []
        
        if provider == "openweathermap":
            # Location information
            location = {
                "lat": weather_data.get("coord", {}).get("lat"),
                "lon": weather_data.get("coord", {}).get("lon"),
                "name": weather_data.get("name", "Unknown"),
                "country": weather_data.get("sys", {}).get("country"),
                "timezone": weather_data.get("timezone", 0),
                "timezone_name": None  # OpenWeatherMap doesn't provide timezone names
            }
            
            # Current weather
            current = {
                "temp": weather_data.get("main", {}).get("temp"),
                "feels_like": weather_data.get("main", {}).get("feels_like"),
                "pressure": weather_data.get("main", {}).get("pressure"),
                "humidity": weather_data.get("main", {}).get("humidity"),
                "wind_speed": weather_data.get("wind", {}).get("speed"),
                "wind_deg": weather_data.get("wind", {}).get("deg"),
                "wind_gust": weather_data.get("wind", {}).get("gust"),
                "clouds": weather_data.get("clouds", {}).get("all"),
                "visibility": weather_data.get("visibility"),
                "weather": weather_data.get("weather", []),
                "rain": weather_data.get("rain", {}),
                "snow": weather_data.get("snow", {}),
                "dt": weather_data.get("dt")
            }
            
            # Alerts (not available in the basic current weather endpoint)
            
        elif provider == "weatherapi":
            # Location information
            location = {
                "lat": weather_data.get("location", {}).get("lat"),
                "lon": weather_data.get("location", {}).get("lon"),
                "name": weather_data.get("location", {}).get("name", "Unknown"),
                "country": weather_data.get("location", {}).get("country"),
                "timezone": weather_data.get("location", {}).get("localtime_epoch") - 
                           weather_data.get("location", {}).get("utc_offset") * 3600,
                "timezone_name": weather_data.get("location", {}).get("tz_id")
            }
            
            # Current weather
            current_data = weather_data.get("current", {})
            
            # Map to standardized format
            current = {
                "temp": current_data.get("temp_c") if params.units == WeatherUnits.METRIC 
                       else current_data.get("temp_f"),
                "feels_like": current_data.get("feelslike_c") if params.units == WeatherUnits.METRIC 
                             else current_data.get("feelslike_f"),
                "pressure": current_data.get("pressure_mb"),
                "humidity": current_data.get("humidity"),
                "wind_speed": current_data.get("wind_kph") if params.units == WeatherUnits.METRIC 
                             else current_data.get("wind_mph"),
                "wind_deg": current_data.get("wind_degree"),
                "wind_gust": current_data.get("gust_kph") if params.units == WeatherUnits.METRIC 
                            else current_data.get("gust_mph"),
                "clouds": current_data.get("cloud"),
                "visibility": current_data.get("vis_km") if params.units == WeatherUnits.METRIC 
                             else current_data.get("vis_miles"),
                "weather": [
                    {
                        "id": 0,  # WeatherAPI doesn't provide IDs
                        "main": current_data.get("condition", {}).get("text"),
                        "description": current_data.get("condition", {}).get("text"),
                        "icon": current_data.get("condition", {}).get("icon")
                    }
                ],
                "rain": {"1h": current_data.get("precip_mm") if current_data.get("precip_mm", 0) > 0 else 0},
                "snow": {"1h": 0},  # WeatherAPI doesn't distinguish rain from snow
                "dt": current_data.get("last_updated_epoch")
            }
            
            # Alerts (might be in a separate endpoint)
            alert_data = weather_data.get("alerts", {}).get("alert", [])
            for alert in alert_data:
                alerts.append({
                    "sender": alert.get("headline", "WeatherAPI Alert"),
                    "event": alert.get("event"),
                    "description": alert.get("desc"),
                    "start": alert.get("effective"),
                    "end": alert.get("expires"),
                    "severity": alert.get("severity", "Unknown")
                })
                
        elif provider == "tomorrow":
            # Location information
            location = {
                "lat": params.lat,  # Tomorrow.io doesn't return lat/lon in the response
                "lon": params.lon,
                "name": "Location",  # Tomorrow.io doesn't provide location names
                "country": None,
                "timezone": weather_data.get("location", {}).get("time", {}).get("timezone"),
                "timezone_name": None
            }
            
            # Current weather
            values = weather_data.get("data", {}).get("values", {})
            
            current = {
                "temp": values.get("temperature"),
                "feels_like": values.get("temperatureApparent"),
                "pressure": values.get("pressureSurfaceLevel"),
                "humidity": values.get("humidity"),
                "wind_speed": values.get("windSpeed"),
                "wind_deg": values.get("windDirection"),
                "wind_gust": values.get("windGust"),
                "clouds": values.get("cloudCover"),
                "visibility": values.get("visibility"),
                "weather": [
                    {
                        "id": 0,
                        "main": self._get_weather_condition_from_code(values.get("weatherCode", 0)),
                        "description": self._get_weather_description_from_code(values.get("weatherCode", 0)),
                        "icon": str(values.get("weatherCode", 0))
                    }
                ],
                "rain": {"1h": values.get("precipitationIntensity", 0)},
                "snow": {"1h": values.get("snowIntensity", 0)},
                "dt": weather_data.get("data", {}).get("time")
            }
            
            # Alerts
            alert_data = weather_data.get("alerts", [])
            for alert in alert_data:
                alerts.append({
                    "sender": alert.get("source"),
                    "event": alert.get("title"),
                    "description": alert.get("description"),
                    "start": alert.get("start"),
                    "end": alert.get("end"),
                    "severity": alert.get("severity", "Unknown")
                })
        
        return {
            "location": location,
            "current": current,
            "units": params.units,
            "source": WeatherSource(provider),
            "alerts": alerts if alerts else None,
            "requested_at": datetime.utcnow()
        }
    
    def _standardize_forecast(
        self,
        forecast_data: Dict[str, Any],
        params: ForecastParameters,
        provider: str
    ) -> Dict[str, Any]:
        """
        Convert provider-specific forecast data to standardized format.
        
        Args:
            forecast_data: Provider's forecast data
            params: Request parameters
            provider: Provider name
            
        Returns:
            Standardized forecast data
        """
        # Extract basic location and forecast information
        location = {}
        forecast = {}
        alerts = []
        
        if provider == "openweathermap":
            # Location information
            location = {
                "lat": forecast_data.get("city", {}).get("coord", {}).get("lat"),
                "lon": forecast_data.get("city", {}).get("coord", {}).get("lon"),
                "name": forecast_data.get("city", {}).get("name", "Unknown"),
                "country": forecast_data.get("city", {}).get("country"),
                "timezone": forecast_data.get("city", {}).get("timezone", 0),
                "timezone_name": None
            }
            
            # Forecast data
            forecast_list = forecast_data.get("list", [])
            
            if params.forecast_type == ForecastType.HOURLY:
                # Group by day and extract hourly data
                forecast_by_day = {}
                
                for item in forecast_list:
                    # Convert timestamp to datetime
                    dt = datetime.fromtimestamp(item.get("dt", 0))
                    day_key = dt.strftime("%Y-%m-%d")
                    
                    if day_key not in forecast_by_day:
                        forecast_by_day[day_key] = {
                            "date": day_key,
                            "day_info": {},
                            "hourly": []
                        }
                    
                    # Add hourly data
                    hour_data = {
                        "dt": item.get("dt"),
                        "temp": item.get("main", {}).get("temp"),
                        "feels_like": item.get("main", {}).get("feels_like"),
                        "pressure": item.get("main", {}).get("pressure"),
                        "humidity": item.get("main", {}).get("humidity"),
                        "wind_speed": item.get("wind", {}).get("speed"),
                        "wind_deg": item.get("wind", {}).get("deg"),
                        "weather": item.get("weather", []),
                        "clouds": item.get("clouds", {}).get("all"),
                        "pop": item.get("pop", 0) * 100,  # Convert to percentage
                        "rain": item.get("rain", {"3h": 0}).get("3h", 0),
                        "snow": item.get("snow", {"3h": 0}).get("3h", 0),
                        "dt_txt": item.get("dt_txt")
                    }
                    
                    forecast_by_day[day_key]["hourly"].append(hour_data)
                
                # Convert to list
                forecast = {
                    "daily": list(forecast_by_day.values())
                }
                
            elif params.forecast_type == ForecastType.DAILY:
                # For OpenWeatherMap, we need to derive daily data from 3-hourly forecast
                # This is a simplified approach - a real implementation would be more sophisticated
                forecast_by_day = {}
                
                for item in forecast_list:
                    # Convert timestamp to datetime
                    dt = datetime.fromtimestamp(item.get("dt", 0))
                    day_key = dt.strftime("%Y-%m-%d")
                    
                    if day_key not in forecast_by_day:
                        forecast_by_day[day_key] = {
                            "date": day_key,
                            "temp_min": item.get("main", {}).get("temp_min", float('inf')),
                            "temp_max": item.get("main", {}).get("temp_max", float('-inf')),
                            "humidity": [],
                            "pressure": [],
                            "wind_speed": [],
                            "weather": [],
                            "pop": 0,
                            "rain": 0,
                            "snow": 0
                        }
                    
                    # Update daily data
                    day_data = forecast_by_day[day_key]
                    main = item.get("main", {})
                    
                    day_data["temp_min"] = min(day_data["temp_min"], main.get("temp_min", day_data["temp_min"]))
                    day_data["temp_max"] = max(day_data["temp_max"], main.get("temp_max", day_data["temp_max"]))
                    day_data["humidity"].append(main.get("humidity", 0))
                    day_data["pressure"].append(main.get("pressure", 0))
                    day_data["wind_speed"].append(item.get("wind", {}).get("speed", 0))
                    day_data["weather"].extend(item.get("weather", []))
                    day_data["pop"] = max(day_data["pop"], item.get("pop", 0) * 100)
                    day_data["rain"] += item.get("rain", {"3h": 0}).get("3h", 0)
                    day_data["snow"] += item.get("snow", {"3h": 0}).get("3h", 0)
                
                # Calculate averages and finalize
                for day_key, day_data in forecast_by_day.items():
                    if day_data["humidity"]:
                        day_data["humidity"] = sum(day_data["humidity"]) / len(day_data["humidity"])
                    if day_data["pressure"]:
                        day_data["pressure"] = sum(day_data["pressure"]) / len(day_data["pressure"])
                    if day_data["wind_speed"]:
                        day_data["wind_speed"] = sum(day_data["wind_speed"]) / len(day_data["wind_speed"])
                    
                    # Get most common weather condition
                    if day_data["weather"]:
                        weather_counts = {}
                        for w in day_data["weather"]:
                            main = w.get("main", "")
                            weather_counts[main] = weather_counts.get(main, 0) + 1
                        
                        # Find most common
                        most_common = max(weather_counts.items(), key=lambda x: x[1])[0]
                        day_data["weather"] = [w for w in day_data["weather"] if w.get("main") == most_common][:1]
                
                # Convert to list
                forecast = {
                    "daily": list(forecast_by_day.values())
                }
                
            elif params.forecast_type == ForecastType.MARINE:
                # Marine forecast processing
                # This would be more complex in a real implementation
                forecast = {
                    "daily": [],
                    "marine_data": {
                        "sea_level": [],
                        "wave_height": [],
                        "wave_direction": [],
                        "wave_period": []
                    }
                }
                
                for item in forecast_list:
                    dt = datetime.fromtimestamp(item.get("dt", 0))
                    
                    # Extract marine data if available
                    marine_data = {
                        "dt": item.get("dt"),
                        "dt_txt": item.get("dt_txt"),
                        "sea_level": item.get("main", {}).get("sea_level"),
                        "wave_height": item.get("sea", {}).get("wave_height") 
                                      if "sea" in item else None,
                        "wave_direction": item.get("sea", {}).get("wave_direction") 
                                        if "sea" in item else None,
                        "wave_period": item.get("sea", {}).get("wave_period") 
                                      if "sea" in item else None
                    }
                    
                    # Add to marine data arrays
                    if marine_data["sea_level"]:
                        forecast["marine_data"]["sea_level"].append(
                            {"dt": marine_data["dt"], "value": marine_data["sea_level"]}
                        )
                    if marine_data["wave_height"]:
                        forecast["marine_data"]["wave_height"].append(
                            {"dt": marine_data["dt"], "value": marine_data["wave_height"]}
                        )
                    if marine_data["wave_direction"]:
                        forecast["marine_data"]["wave_direction"].append(
                            {"dt": marine_data["dt"], "value": marine_data["wave_direction"]}
                        )
                    if marine_data["wave_period"]:
                        forecast["marine_data"]["wave_period"].append(
                            {"dt": marine_data["dt"], "value": marine_data["wave_period"]}
                        )
            
        elif provider == "weatherapi":
            # Location information
            location = {
                "lat": forecast_data.get("location", {}).get("lat"),
                "lon": forecast_data.get("location", {}).get("lon"),
                "name": forecast_data.get("location", {}).get("name", "Unknown"),
                "country": forecast_data.get("location", {}).get("country"),
                "timezone": forecast_data.get("location", {}).get("localtime_epoch") - 
                           forecast_data.get("location", {}).get("utc_offset") * 3600,
                "timezone_name": forecast_data.get("location", {}).get("tz_id")
            }
            
            # Forecast data
            forecast_days = forecast_data.get("forecast", {}).get("forecastday", [])
            
            if params.forecast_type == ForecastType.DAILY:
                # Daily forecast
                daily_data = []
                
                for day in forecast_days:
                    day_data = {
                        "date": day.get("date"),
                        "temp_min": day.get("day", {}).get("mintemp_c") 
                                   if params.units == WeatherUnits.METRIC 
                                   else day.get("day", {}).get("mintemp_f"),
                        "temp_max": day.get("day", {}).get("maxtemp_c")
                                   if params.units == WeatherUnits.METRIC
                                   else day.get("day", {}).get("maxtemp_f"),
                        "humidity": day.get("day", {}).get("avghumidity"),
                        "pressure": None,  # Not provided in daily format
                        "wind_speed": day.get("day", {}).get("maxwind_kph")
                                    if params.units == WeatherUnits.METRIC
                                    else day.get("day", {}).get("maxwind_mph"),
                        "weather": [
                            {
                                "id": 0,
                                "main": day.get("day", {}).get("condition", {}).get("text"),
                                "description": day.get("day", {}).get("condition", {}).get("text"),
                                "icon": day.get("day", {}).get("condition", {}).get("icon")
                            }
                        ],
                        "pop": day.get("day", {}).get("daily_chance_of_rain", 0),
                        "rain": day.get("day", {}).get("totalprecip_mm", 0)
                                if params.units == WeatherUnits.METRIC
                                else day.get("day", {}).get("totalprecip_in", 0),
                        "snow": day.get("day", {}).get("totalsnow_cm", 0)
                    }
                    
                    daily_data.append(day_data)
                
                forecast = {
                    "daily": daily_data
                }
                
            elif params.forecast_type == ForecastType.HOURLY:
                # Hourly forecast
                daily_with_hourly = []
                
                for day in forecast_days:
                    hours = day.get("hour", [])
                    hourly_data = []
                    
                    for hour in hours:
                        hour_data = {
                            "dt": hour.get("time_epoch"),
                            "temp": hour.get("temp_c") if params.units == WeatherUnits.METRIC 
                                   else hour.get("temp_f"),
                            "feels_like": hour.get("feelslike_c") if params.units == WeatherUnits.METRIC 
                                         else hour.get("feelslike_f"),
                            "pressure": hour.get("pressure_mb"),
                            "humidity": hour.get("humidity"),
                            "wind_speed": hour.get("wind_kph") if params.units == WeatherUnits.METRIC 
                                         else hour.get("wind_mph"),
                            "wind_deg": hour.get("wind_degree"),
                            "weather": [
                                {
                                    "id": 0,
                                    "main": hour.get("condition", {}).get("text"),
                                    "description": hour.get("condition", {}).get("text"),
                                    "icon": hour.get("condition", {}).get("icon")
                                }
                            ],
                            "clouds": hour.get("cloud"),
                            "pop": hour.get("chance_of_rain", 0),
                            "rain": hour.get("precip_mm", 0) if params.units == WeatherUnits.METRIC 
                                   else hour.get("precip_in", 0),
                            "snow": 0,  # Not explicitly provided
                            "dt_txt": hour.get("time")
                        }
                        
                        hourly_data.append(hour_data)
                    
                    day_data = {
                        "date": day.get("date"),
                        "day_info": {
                            "temp_min": day.get("day", {}).get("mintemp_c") 
                                       if params.units == WeatherUnits.METRIC 
                                       else day.get("day", {}).get("mintemp_f"),
                            "temp_max": day.get("day", {}).get("maxtemp_c")
                                       if params.units == WeatherUnits.METRIC
                                       else day.get("day", {}).get("maxtemp_f")
                        },
                        "hourly": hourly_data
                    }
                    
                    daily_with_hourly.append(day_data)
                
                forecast = {
                    "daily": daily_with_hourly
                }
                
            elif params.forecast_type == ForecastType.MARINE:
                # Marine forecast processing for WeatherAPI
                marine_data = forecast_data.get("marine", {})
                
                forecast = {
                    "daily": [],
                    "marine_data": {
                        "sea_level": [],
                        "wave_height": [],
                        "wave_direction": [],
                        "wave_period": []
                    }
                }
                
                # Process marine data if available
                if marine_data:
                    for day in forecast_days:
                        # Extract tide data if available
                        if params.tide_data and "tides" in day:
                            tides = day.get("tides", [])
                            for tide in tides:
                                tide_data = tide.get("tide", [])
                                for t in tide_data:
                                    forecast["marine_data"]["sea_level"].append({
                                        "dt": t.get("time_epoch"),
                                        "value": t.get("tide_height_mt") 
                                                if params.units == WeatherUnits.METRIC
                                                else t.get("tide_height_ft"),
                                        "type": t.get("tide_type")
                                    })
                        
                        # Extract hourly marine data
                        hours = day.get("hour", [])
                        for hour in hours:
                            dt = hour.get("time_epoch")
                            
                            # Wave height
                            if "significant_height_mt" in hour:
                                wave_height = hour.get("significant_height_mt") 
                                             if params.units == WeatherUnits.METRIC
                                             else hour.get("significant_height_ft")
                                forecast["marine_data"]["wave_height"].append({
                                    "dt": dt,
                                    "value": wave_height
                                })
                            
                            # Wave direction
                            if "swell_dir_degrees" in hour:
                                forecast["marine_data"]["wave_direction"].append({
                                    "dt": dt,
                                    "value": hour.get("swell_dir_degrees")
                                })
                            
                            # Wave period
                            if "swell_period_secs" in hour:
                                forecast["marine_data"]["wave_period"].append({
                                    "dt": dt,
                                    "value": hour.get("swell_period_secs")
                                })
            
            # Alerts
            alert_data = forecast_data.get("alerts", {}).get("alert", [])
            for alert in alert_data:
                alerts.append({
                    "sender": alert.get("headline", "WeatherAPI Alert"),
                    "event": alert.get("event"),
                    "description": alert.get("desc"),
                    "start": alert.get("effective"),
                    "end": alert.get("expires"),
                    "severity": alert.get("severity", "Unknown")
                })
                
        elif provider == "tomorrow":
            # Location information
            location = {
                "lat": params.lat,  # Tomorrow.io doesn't return lat/lon in the response
                "lon": params.lon,
                "name": "Location",  # Tomorrow.io doesn't provide location names
                "country": None,
                "timezone": forecast_data.get("location", {}).get("timezone"),
                "timezone_name": None
            }
            
            # Forecast data
            timelines = forecast_data.get("timelines", {})
            
            if params.forecast_type == ForecastType.DAILY:
                daily_data = []
                daily_timeline = timelines.get("daily", [])
                
                for day in daily_timeline:
                    values = day.get("values", {})
                    
                    day_data = {
                        "date": day.get("time", "").split("T")[0],
                        "temp_min": values.get("temperatureMin"),
                        "temp_max": values.get("temperatureMax"),
                        "humidity": values.get("humidityAvg"),
                        "pressure": values.get("pressureSurfaceLevelAvg"),
                        "wind_speed": values.get("windSpeedAvg"),
                        "weather": [
                            {
                                "id": values.get("weatherCodeMax", 0),
                                "main": self._get_weather_condition_from_code(values.get("weatherCodeMax", 0)),
                                "description": self._get_weather_description_from_code(values.get("weatherCodeMax", 0)),
                                "icon": str(values.get("weatherCodeMax", 0))
                            }
                        ],
                        "pop": values.get("precipitationProbabilityAvg", 0),
                        "rain": values.get("rainAccumulationSum", 0),
                        "snow": values.get("snowAccumulationSum", 0)
                    }
                    
                    daily_data.append(day_data)
                
                forecast = {
                    "daily": daily_data
                }
                
            elif params.forecast_type == ForecastType.HOURLY:
                # Group hourly data by day
                hourly_timeline = timelines.get("hourly", [])
                hourly_by_day = {}
                
                for hour in hourly_timeline:
                    values = hour.get("values", {})
                    dt_parts = hour.get("time", "").split("T")
                    
                    if len(dt_parts) != 2:
                        continue
                        
                    day_key = dt_parts[0]
                    
                    if day_key not in hourly_by_day:
                        hourly_by_day[day_key] = {
                            "date": day_key,
                            "day_info": {
                                "temp_min": float('inf'),
                                "temp_max": float('-inf')
                            },
                            "hourly": []
                        }
                    
                    # Update min/max temperature
                    temp = values.get("temperature")
                    if temp is not None:
                        hourly_by_day[day_key]["day_info"]["temp_min"] = min(
                            hourly_by_day[day_key]["day_info"]["temp_min"], temp
                        )
                        hourly_by_day[day_key]["day_info"]["temp_max"] = max(
                            hourly_by_day[day_key]["day_info"]["temp_max"], temp
                        )
                    
                    # Add hourly data
                    hour_data = {
                        "dt": int(datetime.fromisoformat(hour.get("time")).timestamp()),
                        "temp": values.get("temperature"),
                        "feels_like": values.get("temperatureApparent"),
                        "pressure": values.get("pressureSurfaceLevel"),
                        "humidity": values.get("humidity"),
                        "wind_speed": values.get("windSpeed"),
                        "wind_deg": values.get("windDirection"),
                        "weather": [
                            {
                                "id": values.get("weatherCode", 0),
                                "main": self._get_weather_condition_from_code(values.get("weatherCode", 0)),
                                "description": self._get_weather_description_from_code(values.get("weatherCode", 0)),
                                "icon": str(values.get("weatherCode", 0))
                            }
                            ],
                        "clouds": values.get("cloudCover"),
                        "pop": values.get("precipitationProbability", 0),
                        "rain": values.get("rainIntensity", 0),
                        "snow": values.get("snowIntensity", 0),
                        "dt_txt": hour.get("time")
                    }
                    
                    hourly_by_day[day_key]["hourly"].append(hour_data)
                
                # Finalize min/max temps
                for day_key, day_data in hourly_by_day.items():
                    if day_data["day_info"]["temp_min"] == float('inf'):
                        day_data["day_info"]["temp_min"] = None
                    if day_data["day_info"]["temp_max"] == float('-inf'):
                        day_data["day_info"]["temp_max"] = None
                
                forecast = {
                    "daily": list(hourly_by_day.values())
                }
            
            # Alerts
            alert_data = forecast_data.get("alerts", [])
            for alert in alert_data:
                alerts.append({
                    "sender": alert.get("sender"),
                    "event": alert.get("title"),
                    "description": alert.get("description"),
                    "start": alert.get("start"),
                    "end": alert.get("end"),
                    "severity": alert.get("severity", "Unknown")
                })
        
        return {
            "location": location,
            "forecast": forecast,
            "units": params.units,
            "source": WeatherSource(provider),
            "forecast_type": params.forecast_type,
            "alerts": alerts if alerts else None,
            "requested_at": datetime.utcnow()
        }
    
    async def _store_weather_in_db(
        self,
        weather: WeatherResponse,
        db_session
    ) -> None:
        """
        Store weather data in database.
        
        Args:
            weather: Weather response
            db_session: Database session
        """
        try:
            # Create record object
            record = WeatherRecord(
                latitude=weather.location.get("lat"),
                longitude=weather.location.get("lon"),
                location_name=weather.location.get("name"),
                temperature=weather.current.get("temp"),
                feels_like=weather.current.get("feels_like"),
                humidity=weather.current.get("humidity"),
                pressure=weather.current.get("pressure"),
                wind_speed=weather.current.get("wind_speed"),
                wind_direction=weather.current.get("wind_deg"),
                weather_main=weather.current.get("weather", [{}])[0].get("main", "Unknown"),
                weather_description=weather.current.get("weather", [{}])[0].get("description", ""),
                clouds=weather.current.get("clouds"),
                visibility=weather.current.get("visibility"),
                rain_1h=weather.current.get("rain", {}).get("1h", 0),
                snow_1h=weather.current.get("snow", {}).get("1h", 0),
                source=weather.source.value,
                units=weather.units.value,
                timestamp=datetime.utcnow(),
                data_timestamp=datetime.fromtimestamp(weather.current.get("dt", 0)) if weather.current.get("dt") else datetime.utcnow()
            )
            
            # Add to session
            db_session.add(record)
            await db_session.commit()
            
            # Process alerts if any
            if weather.alerts:
                for alert in weather.alerts:
                    alert_record = WeatherAlert(
                        weather_record_id=record.id,
                        event=alert.get("event", "Unknown"),
                        description=alert.get("description", ""),
                        severity=alert.get("severity", "Unknown"),
                        start_time=datetime.fromisoformat(alert.get("start")) if isinstance(alert.get("start"), str) else None,
                        end_time=datetime.fromisoformat(alert.get("end")) if isinstance(alert.get("end"), str) else None,
                        source=alert.get("sender", "Unknown")
                    )
                    
                    db_session.add(alert_record)
                
                await db_session.commit()
            
        except Exception as e:
            weather_logger.error(f"Error storing weather in database: {str(e)}")
            await db_session.rollback()
            # Don't re-raise, just log the error
    
    async def _store_forecast_in_db(
        self,
        forecast: ForecastResponse,
        db_session
    ) -> None:
        """
        Store forecast data in database.
        
        Args:
            forecast: Forecast response
            db_session: Database session
        """
        try:
            # Create parent record for the forecast
            parent_record = WeatherRecord(
                latitude=forecast.location.get("lat"),
                longitude=forecast.location.get("lon"),
                location_name=forecast.location.get("name"),
                source=forecast.source.value,
                units=forecast.units.value,
                timestamp=datetime.utcnow(),
                is_forecast=True,
                forecast_type=forecast.forecast_type.value
            )
            
            db_session.add(parent_record)
            await db_session.commit()
            
            # Store daily forecasts
            if "daily" in forecast.forecast:
                for day_data in forecast.forecast.get("daily", []):
                    # For forecast with hourly data
                    if "hourly" in day_data:
                        for hour_data in day_data.get("hourly", []):
                            forecast_record = ForecastRecord(
                                weather_record_id=parent_record.id,
                                forecast_date=datetime.fromisoformat(day_data.get("date")) if isinstance(day_data.get("date"), str) else None,
                                forecast_time=datetime.fromtimestamp(hour_data.get("dt")) if hour_data.get("dt") else None,
                                temperature=hour_data.get("temp"),
                                feels_like=hour_data.get("feels_like"),
                                humidity=hour_data.get("humidity"),
                                pressure=hour_data.get("pressure"),
                                wind_speed=hour_data.get("wind_speed"),
                                wind_direction=hour_data.get("wind_deg"),
                                weather_main=hour_data.get("weather", [{}])[0].get("main", "Unknown"),
                                weather_description=hour_data.get("weather", [{}])[0].get("description", ""),
                                clouds=hour_data.get("clouds"),
                                precipitation_probability=hour_data.get("pop"),
                                rain=hour_data.get("rain"),
                                snow=hour_data.get("snow"),
                                period_type="hourly"
                            )
                            
                            db_session.add(forecast_record)
                    else:
                        # Simple daily forecast
                        forecast_record = ForecastRecord(
                            weather_record_id=parent_record.id,
                            forecast_date=datetime.fromisoformat(day_data.get("date")) if isinstance(day_data.get("date"), str) else None,
                            temperature_min=day_data.get("temp_min"),
                            temperature_max=day_data.get("temp_max"),
                            humidity=day_data.get("humidity"),
                            pressure=day_data.get("pressure"),
                            wind_speed=day_data.get("wind_speed"),
                            weather_main=day_data.get("weather", [{}])[0].get("main", "Unknown"),
                            weather_description=day_data.get("weather", [{}])[0].get("description", ""),
                            precipitation_probability=day_data.get("pop"),
                            rain=day_data.get("rain"),
                            snow=day_data.get("snow"),
                            period_type="daily"
                        )
                        
                        db_session.add(forecast_record)
            
            # Store marine data if available
            if "marine_data" in forecast.forecast:
                marine_data = forecast.forecast.get("marine_data", {})
                
                # Store each type of marine data
                for data_type, data_points in marine_data.items():
                    for point in data_points:
                        forecast_record = ForecastRecord(
                            weather_record_id=parent_record.id,
                            forecast_time=datetime.fromtimestamp(point.get("dt")) if point.get("dt") else None,
                            marine_data_type=data_type,
                            marine_data_value=point.get("value"),
                            marine_data_extra=point.get("type") if "type" in point else None,
                            period_type="marine"
                        )
                        
                        db_session.add(forecast_record)
            
            # Commit all records
            await db_session.commit()
            
        except Exception as e:
            weather_logger.error(f"Error storing forecast in database: {str(e)}")
            await db_session.rollback()
            # Don't re-raise, just log the error
    
    async def _process_weather_alerts(self, weather: WeatherResponse) -> None:
        """
        Process severe weather alerts.
        
        Args:
            weather: Weather response with alerts
        """
        if not weather.alerts:
            return
            
        try:
            # Process each alert
            for alert in weather.alerts:
                severity = alert.get("severity", "Unknown").upper()
                
                # Only process moderate to severe alerts
                if severity in ["MODERATE", "SEVERE", "EXTREME"]:
                    await send_weather_alert({
                        "location": weather.location,
                        "alert": alert,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    weather_logger.info(
                        f"Processed {severity} weather alert for {weather.location.get('name')}: "
                        f"{alert.get('event')}"
                    )
                    
        except Exception as e:
            weather_logger.error(f"Error processing weather alert: {str(e)}")
    
    async def _process_severe_weather_assessment(
        self,
        assessment: Dict[str, Any],
        location: Dict[str, Any]
    ) -> None:
        """
        Process severe weather assessment.
        
        Args:
            assessment: Severe weather assessment
            location: Location information
        """
        try:
            # Check if there are any alerts or severe conditions
            if not assessment.get("has_severe_conditions", False):
                return
                
            # Prepare notification data
            notification_data = {
                "location": location,
                "timestamp": assessment.get("timestamp"),
                "severity": "MODERATE",  # Default
                "conditions": []
            }
            
            # Add alerts
            if assessment.get("alerts"):
                notification_data["alerts"] = assessment.get("alerts")
                
                # Get highest severity from alerts
                severities = [a.get("severity", "UNKNOWN").upper() for a in assessment.get("alerts", [])]
                if "EXTREME" in severities:
                    notification_data["severity"] = "EXTREME"
                elif "SEVERE" in severities:
                    notification_data["severity"] = "SEVERE"
            
            # Add severe conditions
            if assessment.get("severe_conditions"):
                notification_data["conditions"] = assessment.get("severe_conditions")
                
                # Get highest severity from conditions
                severities = [c.get("severity") for c in assessment.get("severe_conditions", [])]
                if WeatherSeverity.EXTREME in severities and notification_data["severity"] != "EXTREME":
                    notification_data["severity"] = "EXTREME"
                elif WeatherSeverity.SEVERE in severities and notification_data["severity"] not in ["EXTREME", "SEVERE"]:
                    notification_data["severity"] = "SEVERE"
            
            # Send notification
            await send_weather_alert(notification_data)
            
            weather_logger.info(
                f"Processed severe weather assessment for {location.get('name')} "
                f"with severity {notification_data['severity']}"
            )
            
        except Exception as e:
            weather_logger.error(f"Error processing severe weather assessment: {str(e)}")
    
    def _sample_route_points(
        self,
        route: List[Tuple[float, float]],
        max_distance_km: float
    ) -> List[Tuple[float, float]]:
        """
        Sample points along a route with a maximum distance between points.
        
        Args:
            route: List of (lat, lon) points
            max_distance_km: Maximum distance between points
            
        Returns:
            Sampled points
        """
        if not route or len(route) < 2:
            return route
            
        sample_points = [route[0]]  # Always include start point
        
        for i in range(1, len(route)):
            last_sample = sample_points[-1]
            current_point = route[i]
            
            # Calculate distance
            distance = haversine_distance_km(
                last_sample[0], last_sample[1],
                current_point[0], current_point[1]
            )
            
            # If distance exceeds threshold or it's the last point, add it
            if distance >= max_distance_km or i == len(route) - 1:
                sample_points.append(current_point)
        
        return sample_points
    
    def _calculate_route_distance(self, route: List[Tuple[float, float]]) -> float:
        """
        Calculate total distance of a route in kilometers.
        
        Args:
            route: List of (lat, lon) points
            
        Returns:
            Total distance in kilometers
        """
        if not route or len(route) < 2:
            return 0.0
            
        total_distance = 0.0
        
        for i in range(len(route) - 1):
            distance = haversine_distance_km(
                route[i][0], route[i][1],
                route[i+1][0], route[i+1][1]
            )
            total_distance += distance
        
        return round(total_distance, 2)
    
    def _get_dominant_condition(self, weather_points: List[WeatherResponse]) -> str:
        """
        Get dominant weather condition from multiple points.
        
        Args:
            weather_points: List of weather responses
            
        Returns:
            Dominant weather condition
        """
        if not weather_points:
            return "Unknown"
            
        # Count occurrences of each condition
        conditions = {}
        
        for point in weather_points:
            condition = point.current.get("weather", [{}])[0].get("main", "Unknown")
            conditions[condition] = conditions.get(condition, 0) + 1
        
        # Return most common condition
        if conditions:
            return max(conditions.items(), key=lambda x: x[1])[0]
        
        return "Unknown"
    
    def _consolidate_alerts(self, weather_points: List[WeatherResponse]) -> List[Dict[str, Any]]:
        """
        Consolidate unique alerts from multiple weather points.
        
        Args:
            weather_points: List of weather responses
            
        Returns:
            List of consolidated alerts
        """
        unique_alerts = {}
        
        for point in weather_points:
            if point.alerts:
                for alert in point.alerts:
                    # Use event as unique key
                    event = alert.get("event")
                    if event and event not in unique_alerts:
                        unique_alerts[event] = alert
        
        return list(unique_alerts.values())
    
    def _get_weather_condition_from_code(self, code: int) -> str:
        """
        Map Tomorrow.io weather codes to standard conditions.
        
        Args:
            code: Weather code
            
        Returns:
            Weather condition string
        """
        # This is a simplified mapping
        code_map = {
            0: "Unknown",
            1000: "Clear",
            1001: "Cloudy",
            1100: "Mostly Clear",
            1101: "Partly Cloudy",
            1102: "Mostly Cloudy",
            2000: "Fog",
            2100: "Light Fog",
            3000: "Light Wind",
            3001: "Wind",
            3002: "Strong Wind",
            4000: "Drizzle",
            4001: "Rain",
            4200: "Light Rain",
            4201: "Heavy Rain",
            5000: "Snow",
            5001: "Flurries",
            5100: "Light Snow",
            5101: "Heavy Snow",
            6000: "Freezing Drizzle",
            6001: "Freezing Rain",
            6200: "Light Freezing Rain",
            6201: "Heavy Freezing Rain",
            7000: "Ice Pellets",
            7101: "Heavy Ice Pellets",
            7102: "Light Ice Pellets",
            8000: "Thunderstorm"
        }
        
        return code_map.get(code, "Unknown")
    
    def _get_weather_description_from_code(self, code: int) -> str:
        """
        Get more detailed description from Tomorrow.io weather code.
        
        Args:
            code: Weather code
            
        Returns:
            Weather description
        """
        # This is a simplified mapping
        description_map = {
            0: "Unknown conditions",
            1000: "Clear skies",
            1001: "Cloudy",
            1100: "Mostly clear skies",
            1101: "Partly cloudy",
            1102: "Mostly cloudy",
            2000: "Foggy conditions",
            2100: "Light fog",
            3000: "Light wind",
            3001: "Windy conditions",
            3002: "Strong winds",
            4000: "Drizzle",
            4001: "Rain",
            4200: "Light rain",
            4201: "Heavy rain",
            5000: "Snow",
            5001: "Snow flurries",
            5100: "Light snow",
            5101: "Heavy snow",
            6000: "Freezing drizzle",
            6001: "Freezing rain",
            6200: "Light freezing rain",
            6201: "Heavy freezing rain",
            7000: "Ice pellets",
            7101: "Heavy ice pellets",
            7102: "Light ice pellets",
            8000: "Thunderstorm activity"
        }
        
        return description_map.get(code, "Unknown conditions")
    
    def _load_api_keys_from_env(self) -> None:
        """Load API keys from environment variables."""
        for provider in WEATHER_PROVIDERS:
            env_var = f"{provider.upper()}_API_KEY"
            api_key = os.getenv(env_var)
            
            if api_key:
                self.api_keys[provider] = api_key
    
    def _validate_configuration(self) -> None:
        """Validate client configuration."""
        # Check if default provider is valid
        if self.default_provider not in WEATHER_PROVIDERS:
            raise ConfigurationError(f"Invalid default provider: {self.default_provider}")
            
        # Check if at least one API key is configured
        if not self.api_keys:
            raise ConfigurationError("No API keys configured")
            
        # Check if default provider has API key
        if self.default_provider not in self.api_keys:
            weather_logger.warning(
                f"Default provider {self.default_provider} has no API key configured. "
                "Switching to first available provider."
            )
            
            # Try to switch to first provider with API key
            for provider in WEATHER_PROVIDERS:
                if provider in self.api_keys:
                    self.default_provider = provider
                    weather_logger.info(f"Using {provider} as default provider instead")
                    return
                    
            raise ConfigurationError("No valid API keys configured")
    
    def _get_alternate_provider(self) -> Optional[str]:
        """
        Get an alternate provider if available.
        
        Returns:
            Alternate provider name or None
        """
        for provider in WEATHER_PROVIDERS:
            if provider != self.default_provider and provider in self.api_keys:
                return provider
                
        return None
    
    def _check_rate_limit(self, provider: str) -> bool:
        """
        Check if a request would exceed rate limits.
        
        Args:
            provider: Provider to check
            
        Returns:
            True if request is allowed, False if it would exceed limits
        """
        if provider not in self.rate_limiters:
            return True
            
        limiter = self.rate_limiters[provider]
        current_time = time.time()
        
        # Reset window if needed
        if current_time - limiter["last_reset"] > limiter["window"]:
            limiter["requests"] = []
            limiter["last_reset"] = current_time
            return True
        
        # Check if would exceed limit
        if len(limiter["requests"]) >= limiter["limit"]:
            return False
            
        return True
    
    def _record_request(self, provider: str) -> None:
        """
        Record a request for rate limiting.
        
        Args:
            provider: Provider to record request for
        """
        if provider not in self.rate_limiters:
            return
            
        limiter = self.rate_limiters[provider]
        current_time = time.time()
        
        # Reset window if needed
        if current_time - limiter["last_reset"] > limiter["window"]:
            limiter["requests"] = []
            limiter["last_reset"] = current_time
        
        # Add request
        limiter["requests"].append(current_time)
    
    def _get_cache_key(self, request_type: str, params: BaseModel) -> str:
        """
        Generate cache key for weather request.
        
        Args:
            request_type: Type of request
            params: Request parameters
            
        Returns:
            Cache key string
        """
        # Create a list of key components
        key_parts = [
            "weather",
            request_type,
            f"lat_{params.lat:.4f}",
            f"lon_{params.lon:.4f}",
            f"units_{params.units.value}"
        ]
        
        # Add additional parameters for forecast requests
        if isinstance(params, ForecastParameters):
            key_parts.extend([
                f"type_{params.forecast_type.value}",
                f"days_{params.days}"
            ])
            
            if params.forecast_type == ForecastType.HOURLY:
                key_parts.append(f"hours_{params.hours}")
        
        # Join with colons
        return ":".join(key_parts)
    
    def _get_mock_data(
        self,
        provider: str,
        endpoint: str,
        params: BaseModel
    ) -> Dict[str, Any]:
        """
        Get mock data for testing.
        
        Args:
            provider: Provider name
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Mock weather data
        """
        # This is a simplified implementation that would be expanded for testing
        if endpoint == "current":
            # Mock current weather
            return {
                "coord": {"lat": params.lat, "lon": params.lon},
                "weather": [
                    {
                        "id": 800,
                        "main": "Clear",
                        "description": "clear sky",
                        "icon": "01d"
                    }
                ],
                "base": "stations",
                "main": {
                    "temp": 22.5,
                    "feels_like": 21.8,
                    "temp_min": 20.0,
                    "temp_max": 25.0,
                    "pressure": 1015,
                    "humidity": 65
                },
                "visibility": 10000,
                "wind": {
                    "speed": 3.6,
                    "deg": 160
                },
                "clouds": {
                    "all": 0
                },
                "dt": int(time.time()),
                "sys": {
                    "country": "XX",
                    "sunrise": int(time.time()) - 21600,
                    "sunset": int(time.time()) + 21600
                },
                "timezone": 0,
                "id": 1,
                "name": "Mock City",
                "cod": 200
            }
        elif endpoint == "forecast":
            # Mock forecast
            return {
                "city": {
                    "id": 1,
                    "name": "Mock City",
                    "coord": {"lat": params.lat, "lon": params.lon},
                    "country": "XX",
                    "timezone": 0
                },
                "cod": "200",
                "message": 0,
                "cnt": 5,
                "list": [
                    {
                        "dt": int(time.time()),
                        "main": {
                            "temp": 22.5,
                            "feels_like": 21.8,
                            "temp_min": 20.0,
                            "temp_max": 25.0,
                            "pressure": 1015,
                            "humidity": 65
                        },
                        "weather": [
                            {
                                "id": 800,
                                "main": "Clear",
                                "description": "clear sky",
                                "icon": "01d"
                            }
                        ],
                        "clouds": {"all": 0},
                        "wind": {"speed": 3.6, "deg": 160},
                        "visibility": 10000,
                        "pop": 0,
                        "dt_txt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    # Additional forecast periods would be added here
                ]
            }
        elif endpoint == "marine":
            # Mock marine forecast
            return {
                "city": {
                    "id": 1,
                    "name": "Mock City",
                    "coord": {"lat": params.lat, "lon": params.lon},
                    "country": "XX",
                    "timezone": 0
                },
                "cod": "200",
                "message": 0,
                "cnt": 5,
                "list": [
                    {
                        "dt": int(time.time()),
                        "main": {
                            "temp": 22.5,
                            "feels_like": 21.8,
                            "temp_min": 20.0,
                            "temp_max": 25.0,
                            "pressure": 1015,
                            "sea_level": 1015,
                            "humidity": 65
                        },
                        "weather": [
                            {
                                "id": 800,
                                "main": "Clear",
                                "description": "clear sky",
                                "icon": "01d"
                            }
                        ],
                        "clouds": {"all": 0},
                        "wind": {"speed": 3.6, "deg": 160},
                        "visibility": 10000,
                        "pop": 0,
                        "sea": {
                            "wave_height": 0.5,
                            "wave_direction": 180,
                            "wave_period": 5
                        },
                        "dt_txt": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    # Additional forecast periods would be added here
                ]
            }
        
        return {}


# Factory function to get weather client
async def get_weather_client(cache: Optional[RedisCache] = None) -> WeatherClient:
    """
    Get a configured weather client.
    
    Args:
        cache: Optional Redis cache instance
        
    Returns:
        WeatherClient instance
    """
    return WeatherClient(cache=cache)


# Convenience functions for direct use

async def fetch_weather(
    lat: float, 
    lon: float,
    units: str = DEFAULT_UNITS,
    include_alerts: bool = True,
    language: str = "en",
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get current weather for a location.
    
    Args:
        lat: Latitude
        lon: Longitude
        units: Unit system (metric, imperial, standard)
        include_alerts: Whether to include alerts
        language: Response language
        provider: Weather provider to use
        
    Returns:
        Dictionary with weather data
    """
    try:
        # Validate coordinates
        if not validate_coordinates(lat, lon):
            raise HTTPException(status_code=400, detail="Invalid coordinates")
            
        # Convert units string to enum if needed
        try:
            units_enum = (
                WeatherUnits(units) 
                if isinstance(units, str) 
                else units
            )
        except ValueError:
            weather_logger.warning(f"Invalid units '{units}', using default")
            units_enum = WeatherUnits(DEFAULT_UNITS)
            
        # Create parameters
        params = WeatherParameters(
            lat=lat,
            lon=lon,
            units=units_enum,
            language=language,
            include_alerts=include_alerts,
            provider=WeatherSource(provider or DEFAULT_PROVIDER)
        )
        
        # Get weather cache if enabled
        cache = None
        if CACHE_ENABLED:
            from app.core.cache import get_redis_cache
            cache = await get_redis_cache()
        
        # Create client and fetch weather
        client = WeatherClient(cache=cache)
        result = await client.get_current_weather(params)
        
        # Return as dictionary
        return result.dict(
            exclude={"raw_data"} if not settings.WEATHER_INCLUDE_RAW_DATA else None
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        weather_logger.error(f"Error fetching weather: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching weather data")