import math
import logging
import numpy as np
import geopy
import pyproj
import shapely
import timezonefinder
from datetime import datetime, timezone
from enum import Enum
from functools import lru_cache
from typing import List, Tuple, Dict, Optional, Union, Any, Callable, Sequence
from dataclasses import dataclass

from shapely.geometry import Point, LineString, Polygon, mapping, shape
from geopy.distance import geodesic, great_circle
from pyproj import Geod, CRS, Transformer
from timezonefinder import TimezoneFinder

from app.core.config import settings
from app.core.logging import geo_logger
from app.exceptions.geo_exceptions import (
    InvalidCoordinatesError,
    GeolocationCalculationError,
    GeocodingError,
    RoutingError
)

# Configure logging
logger = logging.getLogger(__name__)

# Earth constants
EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_M = EARTH_RADIUS_KM * 1000
EARTH_EQUATORIAL_RADIUS_KM = 6378.1370  # WGS84 equatorial radius
EARTH_POLAR_RADIUS_KM = 6356.7523  # WGS84 polar radius
EARTH_FLATTENING = 1/298.257223563  # WGS84 flattening

# Unit conversion constants
NAUTICAL_MILE_IN_KM = 1.852
NAUTICAL_MILE_IN_M = NAUTICAL_MILE_IN_KM * 1000
KNOT_TO_KPH = NAUTICAL_MILE_IN_KM  # 1 knot = 1 NM/hour = 1.852 km/hour
KNOT_TO_MS = NAUTICAL_MILE_IN_KM / 3.6  # Convert to m/s
METER_TO_FATHOM = 0.546807  # Conversion for water depth

# Coordinate system definitions
WGS84 = CRS.from_epsg(4326)  # Standard GPS/positioning CRS
WEBMERC = CRS.from_epsg(3857)  # Web Mercator for web maps

# Global Geod instance for geodesic calculations
GEOD = Geod(ellps="WGS84")

# Timezone finder instance
TZ_FINDER = TimezoneFinder()


class DistanceUnit(str, Enum):
    """Distance unit enumeration."""
    METERS = "m"
    KILOMETERS = "km"
    NAUTICAL_MILES = "nm"
    MILES = "mi"
    FEET = "ft"


class SpeedUnit(str, Enum):
    """Speed unit enumeration."""
    KNOTS = "kn"
    KPH = "kph"
    MPH = "mph"
    MPS = "mps"  # meters per second


class BearingFormat(str, Enum):
    """Bearing format enumeration."""
    DEGREES = "degrees"  # 0-360°
    COMPASS = "compass"  # N, NE, E, SE, etc.
    RADIANS = "radians"  # 0-2π


class EarthModel(str, Enum):
    """Earth model enumeration for distance calculations."""
    SPHERE = "sphere"  # Simple spherical model
    WGS84 = "wgs84"  # WGS84 ellipsoid (most accurate)
    GRS80 = "grs80"  # GRS80 ellipsoid


@dataclass
class GeographicPoint:
    """Class representing a geographic point with rich metadata."""
    latitude: float
    longitude: float
    elevation: Optional[float] = None
    name: Optional[str] = None
    timestamp: Optional[datetime] = None
    properties: Dict[str, Any] = None

    def __post_init__(self):
        """Validate coordinates after initialization."""
        if not validate_coordinates(self.latitude, self.longitude):
            raise InvalidCoordinatesError(f"Invalid coordinates: {self.latitude}, {self.longitude}")
        
        if self.properties is None:
            self.properties = {}

    @property
    def coords(self) -> Tuple[float, float]:
        """Return coordinates as a tuple."""
        return (self.longitude, self.latitude)  # GeoJSON order (lon, lat)

    @property
    def lat_lon(self) -> Tuple[float, float]:
        """Return coordinates in latitude, longitude order."""
        return (self.latitude, self.longitude)

    @property
    def as_point(self) -> Point:
        """Return as Shapely Point."""
        return Point(self.longitude, self.latitude)

    @property
    def as_geojson(self) -> Dict[str, Any]:
        """Return as GeoJSON feature."""
        properties = dict(self.properties) if self.properties else {}
        if self.name:
            properties["name"] = self.name
        if self.elevation is not None:
            properties["elevation"] = self.elevation
        if self.timestamp:
            properties["timestamp"] = self.timestamp.isoformat()

        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": properties
        }

    def distance_to(
        self, 
        other: Union['GeographicPoint', Tuple[float, float]], 
        unit: DistanceUnit = DistanceUnit.KILOMETERS,
        model: EarthModel = EarthModel.WGS84
    ) -> float:
        """
        Calculate distance to another point.
        
        Args:
            other: Another GeographicPoint or (lat, lon) tuple
            unit: Unit for the result
            model: Earth model to use for calculation
            
        Returns:
            Distance in requested units
        """
        if isinstance(other, tuple):
            other_lat, other_lon = other
        else:
            other_lat, other_lon = other.latitude, other.longitude
            
        if model == EarthModel.WGS84:
            # Use geodesic distance (most accurate)
            dist_meters = geodesic(
                (self.latitude, self.longitude), 
                (other_lat, other_lon)
            ).meters
        elif model == EarthModel.SPHERE:
            # Use great circle distance (simpler)
            dist_meters = great_circle_distance_m(
                self.latitude, self.longitude,
                other_lat, other_lon
            )
        else:
            # Use haversine (intermediate accuracy)
            dist_meters = haversine_distance_m(
                self.latitude, self.longitude,
                other_lat, other_lon
            )
            
        # Convert to requested unit
        return convert_distance(dist_meters, DistanceUnit.METERS, unit)

    def bearing_to(
        self, 
        other: Union['GeographicPoint', Tuple[float, float]],
        format: BearingFormat = BearingFormat.DEGREES
    ) -> Union[float, str]:
        """
        Calculate bearing to another point.
        
        Args:
            other: Another GeographicPoint or (lat, lon) tuple
            format: Format for the result
            
        Returns:
            Bearing in requested format
        """
        if isinstance(other, tuple):
            other_lat, other_lon = other
        else:
            other_lat, other_lon = other.latitude, other.longitude
            
        # Calculate initial bearing
        bearing = calculate_bearing(
            self.latitude, self.longitude,
            other_lat, other_lon
        )
        
        # Format as requested
        if format == BearingFormat.DEGREES:
            return bearing
        elif format == BearingFormat.RADIANS:
            return math.radians(bearing)
        elif format == BearingFormat.COMPASS:
            return bearing_to_compass(bearing)
        
        return bearing

    def timezone(self) -> Optional[str]:
        """Get the timezone at this location."""
        return TZ_FINDER.timezone_at(lat=self.latitude, lng=self.longitude)

    @staticmethod
    def from_geojson(geojson: Dict[str, Any]) -> 'GeographicPoint':
        """Create from GeoJSON feature."""
        if geojson["type"] != "Feature" or geojson["geometry"]["type"] != "Point":
            raise ValueError("GeoJSON must be a Feature with Point geometry")
            
        coords = geojson["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        
        props = geojson.get("properties", {})
        elevation = props.get("elevation")
        name = props.get("name")
        
        timestamp = None
        if "timestamp" in props:
            try:
                timestamp = datetime.fromisoformat(props["timestamp"])
            except (ValueError, TypeError):
                pass
                
        # Copy remaining properties
        properties = {k: v for k, v in props.items() 
                     if k not in ("elevation", "name", "timestamp")}
                
        return GeographicPoint(
            latitude=lat,
            longitude=lon,
            elevation=elevation,
            name=name,
            timestamp=timestamp,
            properties=properties
        )


class Route:
    """Class representing a route with waypoints."""
    
    def __init__(
        self, 
        waypoints: List[Union[GeographicPoint, Tuple[float, float]]],
        name: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a route with waypoints.
        
        Args:
            waypoints: List of points defining the route
            name: Optional route name
            properties: Optional additional properties
        """
        self.name = name
        self.properties = properties or {}
        
        # Convert tuples to GeographicPoint objects
        self._waypoints = []
        for i, wp in enumerate(waypoints):
            if isinstance(wp, tuple):
                lat, lon = wp
                point = GeographicPoint(
                    latitude=lat, 
                    longitude=lon,
                    name=f"Waypoint {i+1}"
                )
                self._waypoints.append(point)
            else:
                self._waypoints.append(wp)
    
    @property
    def waypoints(self) -> List[GeographicPoint]:
        """Get route waypoints."""
        return self._waypoints
    
    @property
    def start_point(self) -> Optional[GeographicPoint]:
        """Get route start point."""
        return self._waypoints[0] if self._waypoints else None
    
    @property
    def end_point(self) -> Optional[GeographicPoint]:
        """Get route end point."""
        return self._waypoints[-1] if self._waypoints else None
    
    @property
    def length(self) -> int:
        """Get number of waypoints."""
        return len(self._waypoints)
    
    @property
    def as_linestring(self) -> LineString:
        """Get route as Shapely LineString."""
        return LineString([wp.coords for wp in self._waypoints])
    
    @property
    def as_geojson(self) -> Dict:
        """Get route as GeoJSON feature."""
        properties = dict(self.properties)
        if self.name:
            properties["name"] = self.name
            
        return {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [wp.coords for wp in self._waypoints]
            },
            "properties": properties
        }
    
    def total_distance(
        self, 
        unit: DistanceUnit = DistanceUnit.KILOMETERS,
        model: EarthModel = EarthModel.WGS84
    ) -> float:
        """
        Calculate total route distance.
        
        Args:
            unit: Distance unit
            model: Earth model for calculation
            
        Returns:
            Total distance in requested units
        """
        total = 0.0
        
        if len(self._waypoints) < 2:
            return total
            
        for i in range(len(self._waypoints) - 1):
            total += self._waypoints[i].distance_to(
                self._waypoints[i+1],
                unit=unit,
                model=model
            )
            
        return total
    
    def segment_distances(
        self, 
        unit: DistanceUnit = DistanceUnit.KILOMETERS,
        model: EarthModel = EarthModel.WGS84
    ) -> List[float]:
        """
        Calculate distances for each route segment.
        
        Args:
            unit: Distance unit
            model: Earth model for calculation
            
        Returns:
            List of segment distances
        """
        distances = []
        
        if len(self._waypoints) < 2:
            return distances
            
        for i in range(len(self._waypoints) - 1):
            distances.append(
                self._waypoints[i].distance_to(
                    self._waypoints[i+1],
                    unit=unit,
                    model=model
                )
            )
            
        return distances
    
    def segment_bearings(
        self, 
        format: BearingFormat = BearingFormat.DEGREES
    ) -> List[Union[float, str]]:
        """
        Calculate bearings for each route segment.
        
        Args:
            format: Bearing format
            
        Returns:
            List of segment bearings
        """
        bearings = []
        
        if len(self._waypoints) < 2:
            return bearings
            
        for i in range(len(self._waypoints) - 1):
            bearings.append(
                self._waypoints[i].bearing_to(
                    self._waypoints[i+1],
                    format=format
                )
            )
            
        return bearings
    
    def simplify(
        self, 
        tolerance: float = 0.001,
        preserve_endpoints: bool = True
    ) -> 'Route':
        """
        Simplify the route using Douglas-Peucker algorithm.
        
        Args:
            tolerance: Simplification tolerance
            preserve_endpoints: Whether to preserve start/end points
            
        Returns:
            Simplified route
        """
        if len(self._waypoints) < 3:
            return self
            
        # Convert to LineString for simplification
        line = self.as_linestring
        simplified = line.simplify(tolerance, preserve_topology=True)
        
        # Extract coordinates
        coords = list(simplified.coords)
        
        # Ensure endpoints are preserved if requested
        if preserve_endpoints:
            if coords[0] != self._waypoints[0].coords:
                coords[0] = self._waypoints[0].coords
            if coords[-1] != self._waypoints[-1].coords:
                coords[-1] = self._waypoints[-1].coords
        
        # Convert back to GeographicPoint objects
        new_waypoints = []
        for lon, lat in coords:
            # Find original waypoint with these coords if possible
            original = next(
                (wp for wp in self._waypoints if wp.longitude == lon and wp.latitude == lat),
                None
            )
            
            if original:
                new_waypoints.append(original)
            else:
                new_waypoints.append(GeographicPoint(latitude=lat, longitude=lon))
        
        # Create new route
        return Route(
            waypoints=new_waypoints,
            name=f"{self.name} (simplified)" if self.name else "Simplified route",
            properties=dict(self.properties)
        )
    
    def interpolate_points(
        self,
        interval: float,
        unit: DistanceUnit = DistanceUnit.KILOMETERS
    ) -> 'Route':
        """
        Create a new route with points at regular intervals.
        
        Args:
            interval: Distance between points
            unit: Distance unit
            
        Returns:
            New route with interpolated points
        """
        if len(self._waypoints) < 2:
            return self
        
        # Convert interval to meters
        interval_m = convert_distance(interval, unit, DistanceUnit.METERS)
        
        new_waypoints = []
        new_waypoints.append(self._waypoints[0])  # Include start point
        
        for i in range(len(self._waypoints) - 1):
            start = self._waypoints[i]
            end = self._waypoints[i+1]
            
            # Get points using geodesic interpolation
            points = interpolate_points(
                start.latitude, start.longitude,
                end.latitude, end.longitude,
                interval_m
            )
            
            # Add all points except the first (to avoid duplication)
            for j, (lat, lon) in enumerate(points[1:], 1):
                new_waypoints.append(GeographicPoint(
                    latitude=lat,
                    longitude=lon,
                    name=f"Interpolated {i}-{j}"
                ))
        
        return Route(
            waypoints=new_waypoints,
            name=f"{self.name} (interpolated)" if self.name else "Interpolated route",
            properties=dict(self.properties)
        )
    
    @staticmethod
    def from_geojson(geojson: Dict) -> 'Route':
        """Create a route from GeoJSON feature."""
        if geojson["type"] != "Feature" or geojson["geometry"]["type"] != "LineString":
            raise ValueError("GeoJSON must be a Feature with LineString geometry")
            
        coords = geojson["geometry"]["coordinates"]
        waypoints = []
        
        for lon, lat in coords:
            waypoints.append(GeographicPoint(latitude=lat, longitude=lon))
            
        properties = geojson.get("properties", {})
        name = properties.pop("name", None)
            
        return Route(
            waypoints=waypoints,
            name=name,
            properties=properties
        )


def validate_coordinates(lat: float, lon: float) -> bool:
    """
    Validate if geographic coordinates are within valid range.
    
    Args:
        lat: Latitude (-90 to 90)
        lon: Longitude (-180 to 180)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        return -90 <= float(lat) <= 90 and -180 <= float(lon) <= 180
    except (ValueError, TypeError):
        return False


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two geographic points using the Haversine formula.
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Distance in meters
    """
    try:
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance_km = EARTH_RADIUS_KM * c
        
        return distance_km * 1000  # Convert to meters
    except Exception as e:
        geo_logger.error(f"Error calculating haversine distance: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating distance: {str(e)}")


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two geographic points in kilometers.
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Distance in kilometers
    """
    meters = haversine_distance_m(lat1, lon1, lat2, lon2)
    return round(meters / 1000, 6)


def haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two geographic points in nautical miles.
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Distance in nautical miles
    """
    kilometers = haversine_distance_km(lat1, lon1, lat2, lon2)
    return round(kilometers / NAUTICAL_MILE_IN_KM, 6)


def great_circle_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance using great circle method (slightly more accurate than Haversine).
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Distance in meters
    """
    try:
        # Use the geopy great_circle function
        distance = great_circle((lat1, lon1), (lat2, lon2)).meters
        return distance
    except Exception as e:
        geo_logger.error(f"Error calculating great circle distance: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating distance: {str(e)}")


def geodesic_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance using geodesic method (most accurate, accounts for Earth's ellipsoid shape).
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Distance in meters
    """
    try:
        # Use the geopy geodesic function (Vincenty's formulae)
        distance = geodesic((lat1, lon1), (lat2, lon2)).meters
        return distance
    except Exception as e:
        geo_logger.error(f"Error calculating geodesic distance: {str(e)}")
        # Fall back to great circle if geodesic fails
        return great_circle_distance_m(lat1, lon1, lat2, lon2)


def vincenty_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Alias for geodesic_distance_m - uses Vincenty's formulae.
    (Some maritime systems specifically refer to Vincenty)
    """
    return geodesic_distance_m(lat1, lon1, lat2, lon2)


def convert_distance(
    value: float,
    from_unit: DistanceUnit,
    to_unit: DistanceUnit
) -> float:
    """
    Convert distance between different units.
    
    Args:
        value: Value to convert
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Converted value
    """
    # Convert to meters first
    meters = value
    if from_unit == DistanceUnit.KILOMETERS:
        meters = value * 1000
    elif from_unit == DistanceUnit.NAUTICAL_MILES:
        meters = value * NAUTICAL_MILE_IN_M
    elif from_unit == DistanceUnit.MILES:
        meters = value * 1609.344
    elif from_unit == DistanceUnit.FEET:
        meters = value * 0.3048
    
    # Convert from meters to target unit
    if to_unit == DistanceUnit.METERS:
        return meters
    elif to_unit == DistanceUnit.KILOMETERS:
        return meters / 1000
    elif to_unit == DistanceUnit.NAUTICAL_MILES:
        return meters / NAUTICAL_MILE_IN_M
    elif to_unit == DistanceUnit.MILES:
        return meters / 1609.344
    elif to_unit == DistanceUnit.FEET:
        return meters / 0.3048
    
    return meters  # Default to meters


def convert_speed(
    value: float,
    from_unit: SpeedUnit,
    to_unit: SpeedUnit
) -> float:
    """
    Convert speed between different units.
    
    Args:
        value: Value to convert
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Converted value
    """
    # Convert to meters per second first
    mps = value
    if from_unit == SpeedUnit.KNOTS:
        mps = value * KNOT_TO_MS
    elif from_unit == SpeedUnit.KPH:
        mps = value / 3.6
    elif from_unit == SpeedUnit.MPH:
        mps = value * 0.44704
    
    # Convert from m/s to target unit
    if to_unit == SpeedUnit.MPS:
        return mps
    elif to_unit == SpeedUnit.KNOTS:
        return mps / KNOT_TO_MS
    elif to_unit == SpeedUnit.KPH:
        return mps * 3.6
    elif to_unit == SpeedUnit.MPH:
        return mps / 0.44704
    
    return mps  # Default to m/s


def convert_km_to_nm(km: float) -> float:
    """
    Convert kilometers to nautical miles.
    
    Args:
        km: Distance in kilometers
        
    Returns:
        Distance in nautical miles
    """
    return round(km / NAUTICAL_MILE_IN_KM, 6)


def convert_nm_to_km(nm: float) -> float:
    """
    Convert nautical miles to kilometers.
    
    Args:
        nm: Distance in nautical miles
        
    Returns:
        Distance in kilometers
    """
    return round(nm * NAUTICAL_MILE_IN_KM, 6)


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate initial bearing between two points.
    
    Args:
        lat1, lon1: Coordinates of start point
        lat2, lon2: Coordinates of end point
        
    Returns:
        Bearing in degrees (0-360)
    """
    try:
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Formula for initial bearing
        x = math.sin(lon2 - lon1) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        initial_bearing = math.atan2(x, y)
        
        # Convert to degrees and normalize to 0-360
        initial_bearing = math.degrees(initial_bearing)
        bearing = (initial_bearing + 360) % 360
        
        return round(bearing, 6)
    except Exception as e:
        geo_logger.error(f"Error calculating bearing: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating bearing: {str(e)}")


def bearing_to_compass(bearing: float) -> str:
    """
    Convert bearing in degrees to compass direction.
    
    Args:
        bearing: Bearing in degrees
        
    Returns:
        Compass direction (N, NE, E, etc.)
    """
    # Define compass directions
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    
    # Convert bearing to index in the directions list
    index = round(bearing / 22.5) % 16
    
    return directions[index]


def midpoint_coordinates(lat1: float, lon1: float, lat2: float, lon2: float) -> Tuple[float, float]:
    """
    Calculate the midpoint between two coordinates.
    
    Args:
        lat1, lon1: Coordinates of point A
        lat2, lon2: Coordinates of point B
        
    Returns:
        Tuple with latitude and longitude of midpoint
    """
    try:
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Calculate the midpoint
        Bx = math.cos(lat2) * math.cos(lon2 - lon1)
        By = math.cos(lat2) * math.sin(lon2 - lon1)
        
        lat3 = math.atan2(
            math.sin(lat1) + math.sin(lat2),
            math.sqrt((math.cos(lat1) + Bx) ** 2 + By ** 2)
        )
        lon3 = lon1 + math.atan2(By, math.cos(lat1) + Bx)
        
        # Convert back to degrees
        lat3 = math.degrees(lat3)
        lon3 = math.degrees(lon3)
        
        return round(lat3, 6), round(lon3, 6)
    except Exception as e:
        geo_logger.error(f"Error calculating midpoint: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating midpoint: {str(e)}")


def interpolate_points(
    lat1: float, 
    lon1: float, 
    lat2: float, 
    lon2: float, 
    interval_m: float
) -> List[Tuple[float, float]]:
    """
    Generate points along a path at specified intervals.
    
    Args:
        lat1, lon1: Coordinates of start point
        lat2, lon2: Coordinates of end point
        interval_m: Interval in meters
        
    Returns:
        List of (lat, lon) points
    """
    try:
        # Calculate total distance
        total_distance = geodesic_distance_m(lat1, lon1, lat2, lon2)
        
        # If distance is less than interval, just return endpoints
        if total_distance <= interval_m:
            return [(lat1, lon1), (lat2, lon2)]
        
        # Calculate number of segments
        num_segments = max(1, math.ceil(total_distance / interval_m))
        
        # Use pyproj Geod for proper interpolation along geodesic
        g = Geod(ellps='WGS84')
        
        # Generate points
        points = []
        for i in range(num_segments + 1):
            fraction = i / num_segments
            lon, lat, _ = g.npts(lon1, lat1, lon2, lat2, 1, fraction=fraction)[0]
            points.append((lat, lon))
        
        return points
    except Exception as e:
        geo_logger.error(f"Error interpolating points: {str(e)}")
        raise GeolocationCalculationError(f"Error interpolating points: {str(e)}")


def destination_point(
    lat: float, 
    lon: float, 
    bearing: float, 
    distance: float,
    distance_unit: DistanceUnit = DistanceUnit.KILOMETERS
) -> Tuple[float, float]:
    """
    Calculate destination point given a start point, bearing and distance.
    
    Args:
        lat, lon: Coordinates of start point
        bearing: Bearing in degrees
        distance: Distance to travel
        distance_unit: Unit of distance
        
    Returns:
        Coordinates of destination point (lat, lon)
    """
    try:
        # Convert distance to meters
        distance_m = convert_distance(distance, distance_unit, DistanceUnit.METERS)
        
        # Use pyproj Geod for accurate calculations
        g = Geod(ellps='WGS84')
        
        # Calculate destination point
        lon2, lat2, _ = g.fwd(lon, lat, bearing, distance_m)
        
        return round(lat2, 6), round(lon2, 6)
    except Exception as e:
        geo_logger.error(f"Error calculating destination point: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating destination point: {str(e)}")


def calculate_rhumb_line_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate rhumb line bearing between two points.
    
    Args:
        lat1, lon1: Coordinates of start point
        lat2, lon2: Coordinates of end point
        
    Returns:
        Rhumb line bearing in degrees
    """
    try:
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        
        # Handle crossing the antimeridian
        if abs(lon2 - lon1) > math.pi:
            if lon1 < lon2:
                lon1 += 2 * math.pi
            else:
                lon2 += 2 * math.pi
        
        # Calculate rhumb line bearing
        delta_lon = lon2 - lon1
        delta_psi = math.log(math.tan(lat2/2 + math.pi/4) / math.tan(lat1/2 + math.pi/4))
        
        if abs(delta_lon) > math.pi:
            if delta_lon > 0:
                delta_lon = -(2 * math.pi - delta_lon)
            else:
                delta_lon = 2 * math.pi + delta_lon
        
        bearing = math.atan2(delta_lon, delta_psi)
        
        # Convert to degrees and normalize to 0-360
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return round(bearing, 6)
    except Exception as e:
        geo_logger.error(f"Error calculating rhumb line bearing: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating rhumb line bearing: {str(e)}")


def rhumb_line_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate rhumb line distance between two points.
    
    Args:
        lat1, lon1: Coordinates of start point
        lat2, lon2: Coordinates of end point
        
    Returns:
        Rhumb line distance in meters
    """
    try:
        # Use pyproj Geod for rhumb line calculation
        g = Geod(ellps='WGS84')
        
        # Calculate rhumb line distance using pyproj
        _, _, distance = g.inv(lon1, lat1, lon2, lat2, radians=False)
        
        return abs(distance)  # Ensure positive value
    except Exception as e:
        geo_logger.error(f"Error calculating rhumb line distance: {str(e)}")
        # Fall back to great circle distance
        return great_circle_distance_m(lat1, lon1, lat2, lon2)


def point_in_polygon(
    lat: float, 
    lon: float, 
    polygon: List[Tuple[float, float]]
) -> bool:
    """
    Check if a point is inside a polygon.
    
    Args:
        lat, lon: Coordinates of point
        polygon: List of (lat, lon) tuples defining polygon vertices
        
    Returns:
        True if point is inside polygon
    """
    try:
        # Create Shapely point and polygon
        point = Point(lon, lat)
        poly = Polygon([(lon, lat) for lat, lon in polygon])
        
        # Check if point is inside polygon
        return point.within(poly)
    except Exception as e:
        geo_logger.error(f"Error checking point in polygon: {str(e)}")
        raise GeolocationCalculationError(f"Error checking point in polygon: {str(e)}")


def calculate_area_km2(polygon: List[Tuple[float, float]]) -> float:
    """
    Calculate area of a polygon in square kilometers.
    
    Args:
        polygon: List of (lat, lon) tuples defining polygon vertices
        
    Returns:
        Area in square kilometers
    """
    try:
        # Create Shapely polygon
        poly = Polygon([(lon, lat) for lat, lon in polygon])
        
        # Transform to an equal area projection (use an appropriate UTM zone)
        centroid = poly.centroid
        utm_zone = math.floor((centroid.x + 180) / 6) + 1
        utm_crs = CRS.from_string(f"+proj=utm +zone={utm_zone} +ellps=WGS84 +datum=WGS84 +units=m +no_defs")
        
        # Create transformer
        transformer = Transformer.from_crs(WGS84, utm_crs, always_xy=True)
        
        # Transform polygon to UTM
        utm_coords = [transformer.transform(lon, lat) for lat, lon in polygon]
        utm_poly = Polygon(utm_coords)
        
        # Calculate area and convert to square kilometers
        area_m2 = utm_poly.area
        area_km2 = area_m2 / 1_000_000
        
        return round(area_km2, 6)
    except Exception as e:
        geo_logger.error(f"Error calculating area: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating area: {str(e)}")


def calculate_center_of_gravity(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Calculate center of gravity (centroid) of a set of points.
    
    Args:
        points: List of (lat, lon) tuples
        
    Returns:
        Centroid coordinates (lat, lon)
    """
    if not points:
        raise ValueError("No points provided")
        
    try:
        # Create MultiPoint
        multi_point = shapely.geometry.MultiPoint([(lon, lat) for lat, lon in points])
        
        # Get centroid
        centroid = multi_point.centroid
        
        return round(centroid.y, 6), round(centroid.x, 6)  # Return as lat, lon
    except Exception as e:
        geo_logger.error(f"Error calculating center of gravity: {str(e)}")
        
        # Fall back to simple average if shapely fails
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        
        return round(sum(lats) / len(lats), 6), round(sum(lons) / len(lons), 6)


def get_timezone_at_location(lat: float, lon: float) -> Optional[str]:
    """
    Get timezone at specified coordinates.
    
    Args:
        lat, lon: Coordinates
        
    Returns:
        Timezone string or None if not found
    """
    try:
        return TZ_FINDER.timezone_at(lat=lat, lng=lon)
    except Exception as e:
        geo_logger.error(f"Error finding timezone: {str(e)}")
        return None


def get_local_time_at_location(
    lat: float, 
    lon: float, 
    timestamp: Optional[datetime] = None
) -> Optional[datetime]:
    """
    Get local time at specified coordinates.
    
    Args:
        lat, lon: Coordinates
        timestamp: UTC timestamp (defaults to current time)
        
    Returns:
        Localized datetime or None if timezone not found
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    try:
        # Get timezone
        tz_name = get_timezone_at_location(lat, lon)
        if not tz_name:
            return None
            
        # Convert to local time
        import pytz
        local_tz = pytz.timezone(tz_name)
        local_time = timestamp.astimezone(local_tz)
        
        return local_time
    except Exception as e:
        geo_logger.error(f"Error calculating local time: {str(e)}")
        return None


def convert_dms_to_decimal(
    degrees: int, 
    minutes: int, 
    seconds: float, 
    direction: str
) -> float:
    """
    Convert degrees, minutes, seconds to decimal degrees.
    
    Args:
        degrees: Degrees
        minutes: Minutes
        seconds: Seconds
        direction: N, S, E, or W
        
    Returns:
        Decimal degrees
    """
    try:
        # Convert to decimal
        decimal = degrees + minutes/60 + seconds/3600
        
        # Adjust for direction
        if direction.upper() in ('S', 'W'):
            decimal = -decimal
            
        return round(decimal, 6)
    except Exception as e:
        geo_logger.error(f"Error converting DMS to decimal: {str(e)}")
        raise GeolocationCalculationError(f"Error converting coordinates: {str(e)}")


def convert_decimal_to_dms(
    decimal: float, 
    is_latitude: bool
) -> Tuple[int, int, float, str]:
    """
    Convert decimal degrees to degrees, minutes, seconds.
    
    Args:
        decimal: Decimal degrees
        is_latitude: True for latitude, False for longitude
        
    Returns:
        Tuple of (degrees, minutes, seconds, direction)
    """
    try:
        # Determine direction
        direction = ""
        if is_latitude:
            direction = "N" if decimal >= 0 else "S"
        else:
            direction = "E" if decimal >= 0 else "W"
            
        # Convert to absolute value
        decimal = abs(decimal)
        
        # Extract degrees, minutes, seconds
        degrees = int(decimal)
        decimal_minutes = (decimal - degrees) * 60
        minutes = int(decimal_minutes)
        seconds = (decimal_minutes - minutes) * 60
        
        return degrees, minutes, round(seconds, 3), direction
    except Exception as e:
        geo_logger.error(f"Error converting decimal to DMS: {str(e)}")
        raise GeolocationCalculationError(f"Error converting coordinates: {str(e)}")


def format_coordinates_dms(lat: float, lon: float, seconds_precision: int = 2) -> str:
    """
    Format coordinates as degrees, minutes, seconds.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        seconds_precision: Decimal places for seconds
        
    Returns:
        Formatted coordinates string
    """
    try:
        lat_deg, lat_min, lat_sec, lat_dir = convert_decimal_to_dms(lat, True)
        lon_deg, lon_min, lon_sec, lon_dir = convert_decimal_to_dms(lon, False)
        
        return (
            f"{lat_deg}° {lat_min}' {lat_sec:.{seconds_precision}f}\" {lat_dir}, "
            f"{lon_deg}° {lon_min}' {lon_sec:.{seconds_precision}f}\" {lon_dir}"
        )
    except Exception as e:
        geo_logger.error(f"Error formatting coordinates: {str(e)}")
        # Fall back to decimal format
        return f"{abs(lat):.6f}° {'N' if lat >= 0 else 'S'}, {abs(lon):.6f}° {'E' if lon >= 0 else 'W'}"


def format_coordinates_decimal(lat: float, lon: float, decimal_places: int = 6) -> str:
    """
    Format coordinates as decimal degrees.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        decimal_places: Decimal places to include
        
    Returns:
        Formatted coordinates string
    """
    try:
        return (
            f"{abs(lat):.{decimal_places}f}° {'N' if lat >= 0 else 'S'}, "
            f"{abs(lon):.{decimal_places}f}° {'E' if lon >= 0 else 'W'}"
        )
    except Exception as e:
        geo_logger.error(f"Error formatting coordinates: {str(e)}")
        return f"{lat:.6f}, {lon:.6f}"


def parse_coordinates_string(coord_str: str) -> Tuple[float, float]:
    """
    Parse coordinates from various string formats.
    
    Args:
        coord_str: String containing coordinates
        
    Returns:
        Tuple of (latitude, longitude)
    """
    try:
        # Remove whitespace and convert to uppercase
        coord_str = coord_str.strip().upper()
        
        # Try different formats
        
        # Decimal degrees with direction (e.g., "37.7749° N, 122.4194° W")
        import re
        match = re.match(
            r"(\d+\.\d+)[°\s]*\s*([NS])[,\s]+(\d+\.\d+)[°\s]*\s*([EW])",
            coord_str
        )
        if match:
            lat = float(match.group(1))
            if match.group(2) == "S":
                lat = -lat
                
            lon = float(match.group(3))
            if match.group(4) == "W":
                lon = -lon
                
            return lat, lon
        
        # Decimal degrees as signed numbers (e.g., "37.7749, -122.4194")
        match = re.match(r"(-?\d+\.\d+)[,\s]+(-?\d+\.\d+)", coord_str)
        if match:
            return float(match.group(1)), float(match.group(2))
        
        # DMS format (e.g., "37° 46' 29.9" N, 122° 25' 10.0" W")
        match = re.match(
            r"(\d+)[°\s]+(\d+)['\s]+(\d+\.?\d*)[\"'\s]*\s*([NS])[,\s]+"
            r"(\d+)[°\s]+(\d+)['\s]+(\d+\.?\d*)[\"'\s]*\s*([EW])",
            coord_str
        )
        if match:
            lat_deg = int(match.group(1))
            lat_min = int(match.group(2))
            lat_sec = float(match.group(3))
            lat_dir = match.group(4)
            
            lon_deg = int(match.group(5))
            lon_min = int(match.group(6))
            lon_sec = float(match.group(7))
            lon_dir = match.group(8)
            
            lat = convert_dms_to_decimal(lat_deg, lat_min, lat_sec, lat_dir)
            lon = convert_dms_to_decimal(lon_deg, lon_min, lon_sec, lon_dir)
            
            return lat, lon
        
        # If none of the formats match, raise an error
        raise ValueError(f"Could not parse coordinates: {coord_str}")
    except Exception as e:
        geo_logger.error(f"Error parsing coordinates string: {str(e)}")
        raise GeolocationCalculationError(f"Error parsing coordinates: {str(e)}")


def bounding_box_from_points(
    points: List[Tuple[float, float]], 
    buffer_km: float = 0
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box for a set of points.
    
    Args:
        points: List of (lat, lon) points
        buffer_km: Buffer distance in kilometers to add around the box
        
    Returns:
        Tuple of (min_lat, min_lon, max_lat, max_lon)
    """
    if not points:
        raise ValueError("No points provided")
        
    try:
        # Extract coordinates
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        
        # Calculate min/max
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Add buffer if requested
        if buffer_km > 0:
            # Approximate degrees per km (varies by latitude)
            avg_lat = (min_lat + max_lat) / 2
            lat_deg_per_km = 1 / 111.32  # At equator
            lon_deg_per_km = 1 / (111.32 * math.cos(math.radians(avg_lat)))
            
            buffer_lat = buffer_km * lat_deg_per_km
            buffer_lon = buffer_km * lon_deg_per_km
            
            min_lat -= buffer_lat
            max_lat += buffer_lat
            min_lon -= buffer_lon
            max_lon += buffer_lon
            
            # Clamp to valid ranges
            min_lat = max(-90, min_lat)
            max_lat = min(90, max_lat)
            min_lon = max(-180, min_lon)
            max_lon = min(180, max_lon)
        
        return min_lat, min_lon, max_lat, max_lon
    except Exception as e:
        geo_logger.error(f"Error calculating bounding box: {str(e)}")
        raise GeolocationCalculationError(f"Error calculating bounding box: {str(e)}")


class AdvancedMaritimeCalculations:
    """Class for specialized maritime calculations."""
    
    @staticmethod
    def calculate_tidal_stream_impact(
        vessel_speed_knots: float,
        stream_speed_knots: float,
        stream_direction_deg: float,
        vessel_course_deg: float
    ) -> Dict[str, float]:
        """
        Calculate the impact of a tidal stream on vessel speed and course.
        
        Args:
            vessel_speed_knots: Vessel speed through water
            stream_speed_knots: Tidal stream speed
            stream_direction_deg: Tidal stream direction (flowing towards)
            vessel_course_deg: Vessel course over ground
            
        Returns:
            Dictionary with speed over ground and course correction
        """
        try:
            # Convert to radians
            vessel_course_rad = math.radians(vessel_course_deg)
            stream_direction_rad = math.radians(stream_direction_deg)
            
            # Calculate relative angle between vessel course and stream
            relative_angle_rad = vessel_course_rad - stream_direction_rad
            
            # Calculate speed components
            vessel_x = vessel_speed_knots * math.sin(vessel_course_rad)
            vessel_y = vessel_speed_knots * math.cos(vessel_course_rad)
            
            stream_x = stream_speed_knots * math.sin(stream_direction_rad)
            stream_y = stream_speed_knots * math.cos(stream_direction_rad)
            
            # Calculate resulting speed and course
            resultant_x = vessel_x + stream_x
            resultant_y = vessel_y + stream_y
            
            speed_over_ground = math.sqrt(resultant_x**2 + resultant_y**2)
            course_over_ground = math.degrees(math.atan2(resultant_x, resultant_y)) % 360
            
            # Calculate drift angle
            drift_angle = course_over_ground - vessel_course_deg
            if drift_angle > 180:
                drift_angle -= 360
            elif drift_angle < -180:
                drift_angle += 360
            
            return {
                "speed_over_ground_knots": round(speed_over_ground, 2),
                "course_over_ground_deg": round(course_over_ground, 2),
                "drift_angle_deg": round(drift_angle, 2)
            }
        except Exception as e:
            geo_logger.error(f"Error calculating tidal stream impact: {str(e)}")
            raise GeolocationCalculationError(f"Error in maritime calculation: {str(e)}")
    
    @staticmethod
    def calculate_eta_with_currents(
        route: List[Tuple[float, float]],
        vessel_speed_knots: float,
        current_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate ETA considering current data along a route.
        
        Args:
            route: List of (lat, lon) waypoints
            vessel_speed_knots: Vessel speed through water
            current_data: List of current data for route segments
            
        Returns:
            Dictionary with ETA details
        """
        try:
            if len(route) < 2:
                raise ValueError("Route must have at least 2 waypoints")
                
            if len(current_data) != len(route) - 1:
                raise ValueError("Current data must match the number of route segments")
            
            total_distance_nm = 0
            total_time_hours = 0
            segment_details = []
            
            # Process each route segment
            for i in range(len(route) - 1):
                start_lat, start_lon = route[i]
                end_lat, end_lon = route[i+1]
                
                # Calculate segment distance
                segment_distance_nm = haversine_distance_nm(
                    start_lat, start_lon, end_lat, end_lon
                )
                
                # Calculate bearing
                bearing = calculate_bearing(
                    start_lat, start_lon, end_lat, end_lon
                )
                
                # Get current data for this segment
                current = current_data[i]
                current_speed_knots = current.get("speed_knots", 0)
                current_direction_deg = current.get("direction_deg", 0)
                
                # Calculate effective speed through the segment
                impact = AdvancedMaritimeCalculations.calculate_tidal_stream_impact(
                    vessel_speed_knots,
                    current_speed_knots,
                    current_direction_deg,
                    bearing
                )
                
                effective_speed = impact["speed_over_ground_knots"]
                segment_time_hours = segment_distance_nm / effective_speed
                
                # Add to totals
                total_distance_nm += segment_distance_nm
                total_time_hours += segment_time_hours
                
                segment_details.append({
                    "start": (start_lat, start_lon),
                    "end": (end_lat, end_lon),
                    "distance_nm": round(segment_distance_nm, 2),
                    "bearing_deg": round(bearing, 2),
                    "current_speed_knots": current_speed_knots,
                    "current_direction_deg": current_direction_deg,
                    "effective_speed_knots": round(effective_speed, 2),
                    "segment_time_hours": round(segment_time_hours, 2)
                })
            
            return {
                "total_distance_nm": round(total_distance_nm, 2),
                "total_time_hours": round(total_time_hours, 2),
                "average_speed_knots": round(total_distance_nm / total_time_hours, 2),
                "segment_details": segment_details
            }
        except Exception as e:
            geo_logger.error(f"Error calculating ETA with currents: {str(e)}")
            raise GeolocationCalculationError(f"Error in maritime calculation: {str(e)}")
    
    @staticmethod
    def calculate_great_circle_route(
        start_lat: float, 
        start_lon: float, 
        end_lat: float, 
        end_lon: float,
        num_points: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Calculate waypoints along a great circle route.
        
        Args:
            start_lat, start_lon: Start coordinates
            end_lat, end_lon: End coordinates
            num_points: Number of points along the route
            
        Returns:
            List of (lat, lon) waypoints
        """
        try:
            # Use pyproj Geod for geodesic calculations
            g = Geod(ellps='WGS84')
            
            # Generate points along the great circle
            lonlats = g.npts(
                start_lon, start_lat,
                end_lon, end_lat,
                num_points - 2
            )
            
            # Add start and end points
            route = [(start_lat, start_lon)]
            route.extend([(lat, lon) for lon, lat in lonlats])
            route.append((end_lat, end_lon))
            
            return route
        except Exception as e:
            geo_logger.error(f"Error calculating great circle route: {str(e)}")
            raise GeolocationCalculationError(f"Error calculating route: {str(e)}")
    
    @staticmethod
    def calculate_crosstrack_distance(
        route_start_lat: float, 
        route_start_lon: float,
        route_end_lat: float, 
        route_end_lon: float,
        point_lat: float, 
        point_lon: float,
        unit: DistanceUnit = DistanceUnit.NAUTICAL_MILES
    ) -> float:
        """
        Calculate the cross-track distance of a point from a great circle route.
        
        Args:
            route_start_lat, route_start_lon: Route start coordinates
            route_end_lat, route_end_lon: Route end coordinates
            point_lat, point_lon: Point coordinates
            unit: Unit for the result
            
        Returns:
            Cross-track distance in requested units
        """
        try:
            # Convert to radians
            lat1, lon1 = math.radians(route_start_lat), math.radians(route_start_lon)
            lat2, lon2 = math.radians(route_end_lat), math.radians(route_end_lon)
            lat3, lon3 = math.radians(point_lat), math.radians(point_lon)
            
            # Calculate the distance from point to great circle
            # Using the formula: d = asin(sin(dist_start_to_point) * sin(bearing_diff))
            
            # Distance from start to point
            dist13 = math.acos(
                math.sin(lat1) * math.sin(lat3) + 
                math.cos(lat1) * math.cos(lat3) * math.cos(lon3 - lon1)
            )
            
            # Initial bearing from start to end
            bearing12 = math.atan2(
                math.sin(lon2 - lon1) * math.cos(lat2),
                math.cos(lat1) * math.sin(lat2) - 
                math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
            )
            
            # Initial bearing from start to point
            bearing13 = math.atan2(
                math.sin(lon3 - lon1) * math.cos(lat3),
                math.cos(lat1) * math.sin(lat3) - 
                math.sin(lat1) * math.cos(lat3) * math.cos(lon3 - lon1)
            )
            
            # Difference in bearings
            bearing_diff = bearing13 - bearing12
            
            # Cross-track distance in radians
            xtd_radians = math.asin(math.sin(dist13) * math.sin(bearing_diff))
            
            # Convert to meters
            xtd_meters = xtd_radians * EARTH_RADIUS_M
            
            # Convert to requested unit
            return convert_distance(xtd_meters, DistanceUnit.METERS, unit)
        except Exception as e:
            geo_logger.error(f"Error calculating crosstrack distance: {str(e)}")
            raise GeolocationCalculationError(f"Error in maritime calculation: {str(e)}")


# Cache frequently used calculations
@lru_cache(maxsize=1024)
def cached_haversine_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Cached version of haversine_distance_nm for improved performance."""
    return haversine_distance_nm(lat1, lon1, lat2, lon2)


@lru_cache(maxsize=1024)
def cached_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Cached version of calculate_bearing for improved performance."""
    return calculate_bearing(lat1, lon1, lat2, lon2)


# For backwards compatibility
def get_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Alias for haversine_distance_km."""
    return haversine_distance_km(lat1, lon1, lat2, lon2)


def get_distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Alias for haversine_distance_nm."""
    return haversine_distance_nm(lat1, lon1, lat2, lon2)