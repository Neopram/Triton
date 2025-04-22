# Path: backend/app/utils/time.py

import re
import time
import calendar
import threading
import warnings
import functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, date
from enum import Enum
from typing import (
    Dict, List, Tuple, Union, Optional, Callable, Any, 
    TypeVar, Iterable, Set, Generic, Generator, cast
)

import pytz
import pendulum
import croniter
import humanize
import timeago
import holidays
import iso8601
import dateutil.parser
import dateutil.relativedelta
from dateutil import tz, rrule
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logging import time_logger
from app.exceptions.time_exceptions import (
    TimeParsingError,
    TimeZoneError,
    TimeRangeError,
    InvalidTimeFormatError
)

# Type variables for generic functions
T = TypeVar('T')
ReturnType = TypeVar('ReturnType')

# Constants
DEFAULT_TIMEZONE = pytz.UTC
ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
ISO_8601_BASIC_FORMAT = "%Y%m%dT%H%M%SZ"
RFC_3339_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_TIME_FORMAT = "%H:%M:%S"
DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_TIMESTAMP = 253402300799  # 9999-12-31 23:59:59 UTC
EPOCH_START = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Thread-local context for time operations
_time_context = threading.local()

# Load app timezone from settings, defaulting to UTC
APP_TIMEZONE_STR = getattr(settings, "DEFAULT_TIMEZONE", "UTC")
try:
    APP_TIMEZONE = pytz.timezone(APP_TIMEZONE_STR)
except pytz.exceptions.UnknownTimeZoneError:
    time_logger.warning(f"Unknown timezone {APP_TIMEZONE_STR}, falling back to UTC")
    APP_TIMEZONE = pytz.UTC


class TimeGranularity(str, Enum):
    """Enumeration of time granularity levels."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class DateTimeRange(BaseModel):
    """Model representing a datetime range."""
    start: datetime
    end: datetime
    include_start: bool = True
    include_end: bool = True
    
    @validator('end')
    def end_after_start(cls, v, values):
        if 'start' in values and v < values['start']:
            raise TimeRangeError("End date must be after start date")
        return v
    
    @property
    def duration(self) -> timedelta:
        """Get the duration of the range."""
        return self.end - self.start
    
    def contains(self, dt: datetime) -> bool:
        """Check if the range contains a specific datetime."""
        if not self.include_start and dt == self.start:
            return False
        if not self.include_end and dt == self.end:
            return False
        return self.start <= dt <= self.end
    
    def overlaps(self, other: 'DateTimeRange') -> bool:
        """Check if this range overlaps with another range."""
        if self.end < other.start or self.start > other.end:
            return False
        
        # Handle edge cases with inclusive/exclusive bounds
        if self.end == other.start and (not self.include_end or not other.include_start):
            return False
        if self.start == other.end and (not self.include_start or not other.include_end):
            return False
            
        return True
    
    def intersection(self, other: 'DateTimeRange') -> Optional['DateTimeRange']:
        """Get the intersection of this range with another range."""
        if not self.overlaps(other):
            return None
            
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        
        include_start = True
        if start == self.start:
            include_start = self.include_start
        if start == other.start:
            include_start = include_start and other.include_start
            
        include_end = True
        if end == self.end:
            include_end = self.include_end
        if end == other.end:
            include_end = include_end and other.include_end
            
        return DateTimeRange(
            start=start,
            end=end,
            include_start=include_start,
            include_end=include_end
        )
    
    def split_by_granularity(
        self, 
        granularity: TimeGranularity
    ) -> List['DateTimeRange']:
        """Split the range into smaller ranges by granularity."""
        if granularity == TimeGranularity.SECOND:
            return [self]  # No need to split at second level
            
        ranges = []
        current = self.start
        
        while current < self.end:
            next_boundary = get_next_time_boundary(current, granularity)
            if next_boundary > self.end:
                next_boundary = self.end
                
            include_start = current == self.start and self.include_start
            include_end = next_boundary == self.end and self.include_end
            
            ranges.append(DateTimeRange(
                start=current,
                end=next_boundary,
                include_start=include_start,
                include_end=include_end
            ))
            
            current = next_boundary
            
        return ranges
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DateTimeRange':
        """Create a DateTimeRange from a dictionary."""
        start = parse_datetime(data["start"])
        end = parse_datetime(data["end"])
        include_start = data.get("include_start", True)
        include_end = data.get("include_end", True)
        
        return cls(
            start=start,
            end=end,
            include_start=include_start,
            include_end=include_end
        )


class TimeZoneManager:
    """Manager for timezone operations with caching."""
    
    _timezone_cache: Dict[str, pytz.timezone] = {}
    _common_timezone_aliases = {
        "EST": "America/New_York",
        "CST": "America/Chicago",
        "MST": "America/Denver",
        "PST": "America/Los_Angeles",
        "EDT": "America/New_York",
        "CDT": "America/Chicago",
        "MDT": "America/Denver",
        "PDT": "America/Los_Angeles",
        "GMT": "Etc/GMT",
        "UTC": "UTC",
        "IST": "Asia/Kolkata",
        "JST": "Asia/Tokyo",
        "CEST": "Europe/Paris",
        "EEST": "Europe/Helsinki",
        "AEST": "Australia/Sydney"
    }
    
    @classmethod
    def get_timezone(cls, timezone_str: str) -> pytz.timezone:
        """Get a timezone object from a string, with caching."""
        # Normalize timezone string
        timezone_str = timezone_str.strip()
        
        # Check aliases
        if timezone_str in cls._common_timezone_aliases:
            timezone_str = cls._common_timezone_aliases[timezone_str]
        
        # Check cache
        if timezone_str in cls._timezone_cache:
            return cls._timezone_cache[timezone_str]
            
        try:
            # Get timezone and cache it
            timezone_obj = pytz.timezone(timezone_str)
            cls._timezone_cache[timezone_str] = timezone_obj
            return timezone_obj
        except pytz.exceptions.UnknownTimeZoneError:
            raise TimeZoneError(f"Unknown timezone: {timezone_str}")
    
    @classmethod
    def get_current_offset(cls, timezone_str: str) -> timedelta:
        """Get the current UTC offset for a timezone."""
        tz = cls.get_timezone(timezone_str)
        now = datetime.now(tz)
        return now.utcoffset() or timedelta(0)
    
    @classmethod
    def get_all_timezones(cls) -> List[Dict[str, Union[str, int]]]:
        """Get all timezones with their current offsets."""
        result = []
        now = datetime.now(pytz.UTC)
        
        for tz_name in pytz.all_timezones:
            try:
                tz = pytz.timezone(tz_name)
                localized_now = now.astimezone(tz)
                offset_minutes = int(localized_now.utcoffset().total_seconds() / 60)
                
                result.append({
                    "name": tz_name,
                    "offset_minutes": offset_minutes,
                    "offset_formatted": format_utc_offset(offset_minutes),
                    "display_name": f"{tz_name} ({format_utc_offset(offset_minutes)})"
                })
            except Exception as e:
                time_logger.warning(f"Error processing timezone {tz_name}: {str(e)}")
                continue
        
        # Sort by offset
        result.sort(key=lambda x: x["offset_minutes"])
        return result
    
    @classmethod
    def get_timezones_by_country(cls, country_code: str) -> List[str]:
        """Get all timezones for a specific country."""
        try:
            return pytz.country_timezones[country_code.upper()]
        except KeyError:
            raise ValueError(f"Invalid country code: {country_code}")
    
    @classmethod
    def get_primary_timezone_for_country(cls, country_code: str) -> str:
        """Get the primary timezone for a specific country."""
        try:
            zones = pytz.country_timezones[country_code.upper()]
            return zones[0] if zones else "UTC"
        except KeyError:
            return "UTC"


def utc_now() -> datetime:
    """
    Get the current time in UTC.
    
    Returns:
        Current UTC datetime with timezone information
    """
    return datetime.now(timezone.utc)


def app_now() -> datetime:
    """
    Get the current time in the application's default timezone.
    
    Returns:
        Current datetime in application timezone
    """
    return datetime.now(APP_TIMEZONE)


def set_test_time(dt: Optional[datetime] = None) -> None:
    """
    Set a fixed time for testing.
    
    Args:
        dt: The datetime to use for testing, or None to disable test time
    """
    if dt is not None and dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    _time_context.test_time = dt


def get_current_time() -> datetime:
    """
    Get the current time, respecting any test time override.
    
    Returns:
        Current datetime, or test datetime if set
    """
    test_time = getattr(_time_context, 'test_time', None)
    if test_time is not None:
        return test_time
    return utc_now()


def convert_to_timezone(
    dt: datetime, 
    timezone_str: str,
    is_dst: Optional[bool] = None
) -> datetime:
    """
    Convert a datetime to the specified timezone.
    
    Args:
        dt: Original datetime
        timezone_str: Target timezone (e.g., 'Europe/London')
        is_dst: DST flag for ambiguous times
        
    Returns:
        Datetime in target timezone
        
    Raises:
        TimeZoneError: If timezone is invalid
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
        
    try:
        target_tz = TimeZoneManager.get_timezone(timezone_str)
        
        # Handle DST ambiguity
        if is_dst is not None:
            # This handles ambiguous times properly
            naive_dt = dt.astimezone(target_tz).replace(tzinfo=None)
            return target_tz.localize(naive_dt, is_dst=is_dst)
        
        return dt.astimezone(target_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        raise TimeZoneError(f"Invalid timezone: {timezone_str}")
    except Exception as e:
        raise TimeZoneError(f"Error converting to timezone {timezone_str}: {str(e)}")


def convert_to_utc(dt: datetime) -> datetime:
    """
    Convert a datetime to UTC.
    
    Args:
        dt: Original datetime
        
    Returns:
        UTC datetime
    """
    if dt.tzinfo is None:
        # Assume local time
        dt = APP_TIMEZONE.localize(dt)
    
    return dt.astimezone(pytz.UTC)


def format_iso8601(dt: datetime) -> str:
    """
    Format a datetime in ISO 8601 format (RFC 3339).
    
    Args:
        dt: Datetime to format
        
    Returns:
        Formatted string (e.g., '2024-10-21T14:30:00Z')
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    return dt.astimezone(pytz.UTC).isoformat().replace('+00:00', 'Z')


def format_datetime(
    dt: datetime,
    format_str: Optional[str] = None,
    timezone_str: Optional[str] = None
) -> str:
    """
    Format a datetime using the specified format and timezone.
    
    Args:
        dt: Datetime to format
        format_str: Format string (default is ISO8601)
        timezone_str: Target timezone (default is UTC)
        
    Returns:
        Formatted datetime string
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    if timezone_str:
        dt = convert_to_timezone(dt, timezone_str)
    
    if not format_str:
        return format_iso8601(dt)
    
    return dt.strftime(format_str)


def format_utc_offset(offset_minutes: int) -> str:
    """
    Format UTC offset in standard format.
    
    Args:
        offset_minutes: Offset in minutes
        
    Returns:
        Formatted offset (e.g., '+05:30', '-08:00')
    """
    sign = "+" if offset_minutes >= 0 else "-"
    abs_offset = abs(offset_minutes)
    hours = abs_offset // 60
    minutes = abs_offset % 60
    
    return f"{sign}{hours:02d}:{minutes:02d}"


def time_diff_human_readable(
    start: datetime, 
    end: Optional[datetime] = None,
    granularity: int = 2,
    include_seconds: bool = False
) -> str:
    """
    Get a human-readable time difference between two datetimes.
    
    Args:
        start: Start datetime
        end: End datetime (default: current time)
        granularity: Level of detail (e.g., 2 = "2 hours, 15 minutes")
        include_seconds: Whether to include seconds
        
    Returns:
        Human-readable time difference
    """
    end = end or get_current_time()
    
    if start.tzinfo is None:
        start = pytz.UTC.localize(start)
    if end.tzinfo is None:
        end = pytz.UTC.localize(end)
    
    # Use humanize library for natural language representation
    return humanize.precisedelta(
        abs(end - start),
        minimum_unit="seconds" if include_seconds else "minutes",
        format="%0.0f",
        suppress=["days"] if (abs(end - start) < timedelta(days=1)) else []
    )


def time_ago(dt: datetime, reference: Optional[datetime] = None) -> str:
    """
    Get a relative time description (e.g., "2 hours ago").
    
    Args:
        dt: The datetime to describe
        reference: Reference time (default: current time)
        
    Returns:
        Human-readable relative time
    """
    reference = reference or get_current_time()
    
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    if reference.tzinfo is None:
        reference = pytz.UTC.localize(reference)
    
    return timeago.format(dt, reference)


def parse_datetime(
    dt_str: Union[str, int, float, datetime],
    default_timezone: str = "UTC",
    raise_error: bool = True
) -> Optional[datetime]:
    """
    Parse a string, timestamp, or datetime into a datetime object.
    
    Args:
        dt_str: String, timestamp, or datetime to parse
        default_timezone: Default timezone for naive datetimes
        raise_error: Whether to raise an error on failure
        
    Returns:
        Parsed datetime, or None if parsing failed and raise_error is False
        
    Raises:
        TimeParsingError: If parsing fails and raise_error is True
    """
    # If it's already a datetime, just ensure it has timezone
    if isinstance(dt_str, datetime):
        if dt_str.tzinfo is None:
            return TimeZoneManager.get_timezone(default_timezone).localize(dt_str)
        return dt_str
    
    # If it's a timestamp (int or float)
    if isinstance(dt_str, (int, float)):
        # Validate timestamp
        if dt_str < 0 or dt_str > MAX_TIMESTAMP:
            if raise_error:
                raise TimeParsingError(f"Invalid timestamp: {dt_str}")
            return None
        
        # Convert to datetime
        return datetime.fromtimestamp(dt_str, pytz.UTC)
    
    # If it's a string, try multiple parsing strategies
    if isinstance(dt_str, str):
        dt_str = dt_str.strip()
        
        # Try ISO 8601 first (most reliable)
        try:
            dt = iso8601.parse_date(dt_str)
            return dt
        except iso8601.ParseError:
            pass
        
        # Try pendulum (supports many formats)
        try:
            dt = pendulum.parse(dt_str)
            return dt.in_timezone(TimeZoneManager.get_timezone(default_timezone))
        except (ValueError, pendulum.parsing.exceptions.ParserError):
            pass
        
        # Try dateutil as a fallback (very flexible but less strict)
        try:
            dt = dateutil.parser.parse(dt_str)
            if dt.tzinfo is None:
                return TimeZoneManager.get_timezone(default_timezone).localize(dt)
            return dt
        except (ValueError, dateutil.parser.ParserError):
            pass
        
        # Failed to parse
        if raise_error:
            raise TimeParsingError(f"Unable to parse datetime: {dt_str}")
        return None
    
    # Unsupported type
    if raise_error:
        raise TimeParsingError(f"Unsupported datetime type: {type(dt_str)}")
    return None


def parse_datetime_safe(
    dt_str: str, 
    default_timezone: str = "UTC"
) -> datetime:
    """
    Safely parse a datetime string with timezone handling.
    
    Args:
        dt_str: Datetime string to parse
        default_timezone: Default timezone if not specified in the string
        
    Returns:
        Parsed datetime with timezone
        
    Raises:
        ValueError: If parsing fails
    """
    try:
        dt = parse_datetime(dt_str, default_timezone)
        if dt is None:
            raise ValueError(f"Failed to parse datetime: {dt_str}")
        return dt
    except TimeParsingError as e:
        raise ValueError(str(e))


def parse_date(
    date_str: Union[str, date, datetime],
    format_str: Optional[str] = None
) -> date:
    """
    Parse a string or datetime into a date object.
    
    Args:
        date_str: String or datetime to parse
        format_str: Optional format string for parsing
        
    Returns:
        Parsed date
        
    Raises:
        TimeParsingError: If parsing fails
    """
    # If it's already a date, just return it
    if isinstance(date_str, date) and not isinstance(date_str, datetime):
        return date_str
    
    # If it's a datetime, convert to date
    if isinstance(date_str, datetime):
        return date_str.date()
    
    # If it's a string
    if isinstance(date_str, str):
        date_str = date_str.strip()
        
        # Try with specified format
        if format_str:
            try:
                return datetime.strptime(date_str, format_str).date()
            except ValueError:
                pass
        
        # Try ISO format
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
        
        # Try parsing as datetime and extract date
        try:
            dt = parse_datetime(date_str)
            if dt:
                return dt.date()
        except TimeParsingError:
            pass
        
        # Try common formats
        common_formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
            "%d.%m.%Y", "%m.%d.%Y", "%B %d, %Y", "%d %B %Y"
        ]
        
        for fmt in common_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        raise TimeParsingError(f"Unable to parse date: {date_str}")
    
    raise TimeParsingError(f"Unsupported date type: {type(date_str)}")


def validate_date_range(
    start: datetime, 
    end: datetime, 
    max_days: int = 365,
    min_days: int = 0
) -> bool:
    """
    Validate a date range.
    
    Args:
        start: Start datetime
        end: End datetime
        max_days: Maximum allowed range in days
        min_days: Minimum allowed range in days
        
    Returns:
        True if valid
        
    Raises:
        TimeRangeError: If validation fails
    """
    if start > end:
        raise TimeRangeError("Start date cannot be after end date")
    
    days_diff = (end - start).days
    
    if days_diff > max_days:
        raise TimeRangeError(f"Date range exceeds maximum of {max_days} days")
    
    if days_diff < min_days:
        raise TimeRangeError(f"Date range is less than minimum of {min_days} days")
    
    return True


def date_range(
    start: date,
    end: date,
    step: int = 1
) -> Generator[date, None, None]:
    """
    Generate a range of dates.
    
    Args:
        start: Start date
        end: End date (inclusive)
        step: Step in days
        
    Yields:
        Dates in the range
    """
    current = start
    while current <= end:
        yield current
        current += timedelta(days=step)


def datetime_range(
    start: datetime,
    end: datetime,
    step: timedelta = timedelta(days=1)
) -> Generator[datetime, None, None]:
    """
    Generate a range of datetimes.
    
    Args:
        start: Start datetime
        end: End datetime (inclusive)
        step: Step as timedelta
        
    Yields:
        Datetimes in the range
    """
    current = start
    while current <= end:
        yield current
        current += step


def get_start_of_period(
    dt: datetime,
    granularity: TimeGranularity
) -> datetime:
    """
    Get the start of a time period (day, week, month, etc.).
    
    Args:
        dt: Reference datetime
        granularity: Time granularity
        
    Returns:
        Datetime at the start of the period
    """
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # Get start of period
    if granularity == TimeGranularity.SECOND:
        return dt.replace(microsecond=0)
    elif granularity == TimeGranularity.MINUTE:
        return dt.replace(second=0, microsecond=0)
    elif granularity == TimeGranularity.HOUR:
        return dt.replace(minute=0, second=0, microsecond=0)
    elif granularity == TimeGranularity.DAY:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif granularity == TimeGranularity.WEEK:
        # Get start of week (Monday)
        return (dt - timedelta(days=dt.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif granularity == TimeGranularity.MONTH:
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif granularity == TimeGranularity.QUARTER:
        # Get first month of quarter
        month = ((dt.month - 1) // 3) * 3 + 1
        return dt.replace(
            month=month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    elif granularity == TimeGranularity.YEAR:
        return dt.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
    
    raise ValueError(f"Unsupported granularity: {granularity}")


def get_end_of_period(
    dt: datetime,
    granularity: TimeGranularity
) -> datetime:
    """
    Get the end of a time period (day, week, month, etc.).
    
    Args:
        dt: Reference datetime
        granularity: Time granularity
        
    Returns:
        Datetime at the end of the period
    """
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # Get start of next period and subtract 1 microsecond
    next_period = get_next_time_boundary(dt, granularity)
    return next_period - timedelta(microseconds=1)


def get_next_time_boundary(
    dt: datetime,
    granularity: TimeGranularity
) -> datetime:
    """
    Get the next time boundary for a granularity level.
    
    Args:
        dt: Reference datetime
        granularity: Time granularity
        
    Returns:
        Datetime at the next boundary
    """
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # Get next boundary
    if granularity == TimeGranularity.SECOND:
        return dt.replace(microsecond=0) + timedelta(seconds=1)
    elif granularity == TimeGranularity.MINUTE:
        return dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    elif granularity == TimeGranularity.HOUR:
        return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    elif granularity == TimeGranularity.DAY:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    elif granularity == TimeGranularity.WEEK:
        # Get start of next week (Monday)
        days_to_next_monday = 7 - dt.weekday()
        return (dt + timedelta(days=days_to_next_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif granularity == TimeGranularity.MONTH:
        # Get first day of next month
        if dt.month == 12:
            return dt.replace(
                year=dt.year+1, month=1, day=1, 
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            return dt.replace(
                month=dt.month+1, day=1, 
                hour=0, minute=0, second=0, microsecond=0
            )
    elif granularity == TimeGranularity.QUARTER:
        # Get first month of next quarter
        month = ((dt.month - 1) // 3) * 3 + 4
        year = dt.year
        if month > 12:
            month -= 12
            year += 1
        return dt.replace(
            year=year, month=month, day=1, 
            hour=0, minute=0, second=0, microsecond=0
        )
    elif granularity == TimeGranularity.YEAR:
        return dt.replace(
            year=dt.year+1, month=1, day=1, 
            hour=0, minute=0, second=0, microsecond=0
        )
    
    raise ValueError(f"Unsupported granularity: {granularity}")


def get_period_range(
    start: datetime,
    end: datetime,
    granularity: TimeGranularity
) -> List[Tuple[datetime, datetime]]:
    """
    Get a list of period ranges between two datetimes.
    
    Args:
        start: Start datetime
        end: End datetime
        granularity: Time granularity
        
    Returns:
        List of (period_start, period_end) tuples
    """
    if start > end:
        raise TimeRangeError("Start date must be before end date")
    
    # Ensure datetimes have timezone
    if start.tzinfo is None:
        start = pytz.UTC.localize(start)
    if end.tzinfo is None:
        end = pytz.UTC.localize(end)
    
    # Align start to period boundary
    period_start = get_start_of_period(start, granularity)
    if period_start < start:
        period_start = get_next_time_boundary(start, granularity)
    
    # Generate periods
    periods = []
    current_start = period_start
    
    while current_start <= end:
        current_end = get_end_of_period(current_start, granularity)
        if current_end > end:
            current_end = end
        
        periods.append((current_start, current_end))
        current_start = get_next_time_boundary(current_start, granularity)
    
    return periods


def is_working_day(
    dt: Union[datetime, date],
    country_code: str = "US",
    include_weekends: bool = False
) -> bool:
    """
    Check if a date is a working day (not weekend or holiday).
    
    Args:
        dt: Date to check
        country_code: Country code for holidays
        include_weekends: Whether to consider weekends as working days
        
    Returns:
        True if working day
    """
    # Convert to date if datetime
    if isinstance(dt, datetime):
        d = dt.date()
    else:
        d = dt
    
    # Check if weekend
    if not include_weekends and d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False
    
    # Check if holiday
    try:
        country_holidays = holidays.country_holidays(country_code, years=d.year)
        return d not in country_holidays
    except Exception:
        # Fall back to just weekend check if holiday data not available
        return True if include_weekends else d.weekday() < 5


def add_working_days(
    dt: datetime,
    days: int,
    country_code: str = "US"
) -> datetime:
    """
    Add a number of working days to a date.
    
    Args:
        dt: Start datetime
        days: Number of working days to add (can be negative)
        country_code: Country code for holidays
        
    Returns:
        Datetime after adding working days
    """
    # Ensure datetime has timezone
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    # Initialize variables
    result = dt
    day_counter = 0
    step = 1 if days >= 0 else -1
    days_to_add = abs(days)
    
    # Load holidays
    try:
        country_holidays = holidays.country_holidays(
            country_code, years=[dt.year, dt.year + step]
        )
    except Exception:
        # Fall back to just weekend check if holiday data not available
        country_holidays = {}
    
    # Add or subtract days
    while day_counter < days_to_add:
        result = result + timedelta(days=step)
        
        # Check if working day
        if result.weekday() < 5 and result.date() not in country_holidays:
            day_counter += 1
    
    return result


def get_next_working_day(
    dt: datetime,
    country_code: str = "US"
) -> datetime:
    """
    Get the next working day.
    
    Args:
        dt: Reference datetime
        country_code: Country code for holidays
        
    Returns:
        Next working day
    """
    return add_working_days(dt, 1, country_code)


def get_previous_working_day(
    dt: datetime,
    country_code: str = "US"
) -> datetime:
    """
    Get the previous working day.
    
    Args:
        dt: Reference datetime
        country_code: Country code for holidays
        
    Returns:
        Previous working day
    """
    return add_working_days(dt, -1, country_code)


def get_working_days_in_range(
    start: datetime,
    end: datetime,
    country_code: str = "US"
) -> List[datetime]:
    """
    Get all working days in a date range.
    
    Args:
        start: Start datetime
        end: End datetime
        country_code: Country code for holidays
        
    Returns:
        List of working days
    """
    if start > end:
        raise TimeRangeError("Start date must be before end date")
    
    # Ensure datetimes have timezone
    if start.tzinfo is None:
        start = pytz.UTC.localize(start)
    if end.tzinfo is None:
        end = pytz.UTC.localize(end)
    
    # Initialize result
    working_days = []
    
    # Load holidays
    try:
        years = list(range(start.year, end.year + 1))
        country_holidays = holidays.country_holidays(country_code, years=years)
    except Exception:
        # Fall back to just weekend check if holiday data not available
        country_holidays = {}
    
    # Align to start of day
    current = start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Iterate through dates
    while current <= end:
        if current.weekday() < 5 and current.date() not in country_holidays:
            working_days.append(current)
        
        current += timedelta(days=1)
    
    return working_days


def get_business_hours_overlap(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
    business_start_hour: int = 9,
    business_end_hour: int = 17,
    timezone_str: str = "UTC"
) -> timedelta:
    """
    Calculate the overlap of two time ranges during business hours.
    
    Args:
        start1, end1: First time range
        start2, end2: Second time range
        business_start_hour: Start of business hours
        business_end_hour: End of business hours
        timezone_str: Timezone for business hours
        
    Returns:
        Overlap duration
    """
    # Ensure all datetimes have timezone
    tz = TimeZoneManager.get_timezone(timezone_str)
    
    if start1.tzinfo is None:
        start1 = tz.localize(start1)
    if end1.tzinfo is None:
        end1 = tz.localize(end1)
    if start2.tzinfo is None:
        start2 = tz.localize(start2)
    if end2.tzinfo is None:
        end2 = tz.localize(end2)
    
    # Convert all times to the specified timezone
    start1 = start1.astimezone(tz)
    end1 = end1.astimezone(tz)
    start2 = start2.astimezone(tz)
    end2 = end2.astimezone(tz)
    
    # Find overlap of the two time ranges
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    
    if overlap_start >= overlap_end:
        return timedelta(0)  # No overlap
    
    # Calculate business hours overlap
    overlap_duration = timedelta(0)
    current_date = overlap_start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = overlap_end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    while current_date < end_date:
        # Skip weekends
        if current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            current_date += timedelta(days=1)
            continue
        
        # Business hours for this day
        business_start = current_date.replace(hour=business_start_hour, minute=0, second=0, microsecond=0)
        business_end = current_date.replace(hour=business_end_hour, minute=0, second=0, microsecond=0)
        
        # Overlap for this day
        day_overlap_start = max(business_start, overlap_start)
        day_overlap_end = min(business_end, overlap_end, current_date + timedelta(days=1))
        
        if day_overlap_start < day_overlap_end:
            overlap_duration += day_overlap_end - day_overlap_start
        
        current_date += timedelta(days=1)
    
    return overlap_duration


def is_valid_cron_expression(cron_expression: str) -> bool:
    """
    Validate a cron expression.
    
    Args:
        cron_expression: Cron expression to validate
        
    Returns:
        True if valid
    """
    try:
        croniter.croniter(cron_expression)
        return True
    except (ValueError, KeyError):
        return False


def get_next_cron_occurrence(
    cron_expression: str,
    dt: Optional[datetime] = None,
    count: int = 1
) -> Union[datetime, List[datetime]]:
    """
    Get the next occurrence(s) of a cron schedule.
    
    Args:
        cron_expression: Cron expression
        dt: Reference datetime (default: current time)
        count: Number of occurrences to get
        
    Returns:
        Next occurrence(s)
        
    Raises:
        ValueError: If cron expression is invalid
    """
    dt = dt or get_current_time()
    
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    try:
        cron = croniter.croniter(cron_expression, dt)
        
        if count == 1:
            return cron.get_next(datetime)
        else:
            return [cron.get_next(datetime) for _ in range(count)]
    except (ValueError, KeyError) as e:
        raise ValueError(f"Invalid cron expression: {cron_expression} - {str(e)}")


def datetime_to_timestamp(dt: datetime) -> float:
    """
    Convert a datetime to a UNIX timestamp.
    
    Args:
        dt: Datetime to convert
        
    Returns:
        UNIX timestamp (seconds since epoch)
    """
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    
    return dt.timestamp()


def timestamp_to_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Convert a UNIX timestamp to a datetime.
    
    Args:
        timestamp: UNIX timestamp (seconds since epoch)
        
    Returns:
        UTC datetime
        
    Raises:
        ValueError: If timestamp is invalid
    """
    try:
        return datetime.fromtimestamp(timestamp, pytz.UTC)
    except (ValueError, OSError, OverflowError) as e:
        raise ValueError(f"Invalid timestamp: {timestamp} - {str(e)}")


def measure_execution_time(func: Callable[..., ReturnType]) -> Callable[..., ReturnType]:
    """
    Decorator to measure and log execution time of a function.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        time_logger.debug(
            f"Function {func.__name__} executed in {(end_time - start_time) * 1000:.2f} ms"
        )
        
        return result
    
    return wrapper


def get_time_boundaries(
    dt: datetime,
    granularity: TimeGranularity
) -> Tuple[datetime, datetime]:
    """
    Get the start and end of a time period.
    
    Args:
        dt: Reference datetime
        granularity: Time granularity
        
    Returns:
        Tuple of (period_start, period_end)
    """
    period_start = get_start_of_period(dt, granularity)
    period_end = get_end_of_period(dt, granularity)
    
    return period_start, period_end


def calculate_age(
    birth_date: Union[datetime, date],
    reference_date: Optional[Union[datetime, date]] = None
) -> int:
    """
    Calculate age in years.
    
    Args:
        birth_date: Birth date
        reference_date: Reference date (default: current date)
        
    Returns:
        Age in years
    """
    # Convert to date if datetime
    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    
    # Get reference date
    if reference_date is None:
        reference_date = datetime.now(timezone.utc).date()
    elif isinstance(reference_date, datetime):
        reference_date = reference_date.date()
    
    # Calculate age
    age = reference_date.year - birth_date.year
    
    # Adjust if birthday hasn't occurred yet this year
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    
    return age


def generate_date_periods(
    start: datetime,
    end: datetime,
    granularity: TimeGranularity
) -> List[DateTimeRange]:
    """
    Generate a list of date periods.
    
    Args:
        start: Start datetime
        end: End datetime
        granularity: Time granularity
        
    Returns:
        List of DateTimeRange objects
    """
    ranges = []
    
    # Get period boundaries
    period_ranges = get_period_range(start, end, granularity)
    
    for period_start, period_end in period_ranges:
        ranges.append(DateTimeRange(
            start=period_start,
            end=period_end
        ))
    
    return ranges


def get_months_between(
    start: datetime,
    end: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    Get all month boundaries between two dates.
    
    Args:
        start: Start datetime
        end: End datetime
        
    Returns:
        List of (month_start, month_end) tuples
    """
    return get_period_range(start, end, TimeGranularity.MONTH)


def get_quarters_between(
    start: datetime,
    end: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    Get all quarter boundaries between two dates.
    
    Args:
        start: Start datetime
        end: End datetime
        
    Returns:
        List of (quarter_start, quarter_end) tuples
    """
    return get_period_range(start, end, TimeGranularity.QUARTER)


def get_years_between(
    start: datetime,
    end: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    Get all year boundaries between two dates.
    
    Args:
        start: Start datetime
        end: End datetime
        
    Returns:
        List of (year_start, year_end) tuples
    """
    return get_period_range(start, end, TimeGranularity.YEAR)


def get_fiscal_year_dates(
    year: int,
    start_month: int = 7,
    start_day: int = 1
) -> Tuple[datetime, datetime]:
    """
    Get the start and end dates of a fiscal year.
    
    Args:
        year: Fiscal year
        start_month: Starting month of fiscal year
        start_day: Starting day of fiscal year
        
    Returns:
        Tuple of (fiscal_year_start, fiscal_year_end)
    """
    # Fiscal year start
    if start_month <= 12:
        fiscal_start = datetime(year - 1, start_month, start_day, tzinfo=pytz.UTC)
    else:
        raise ValueError("Start month must be 1-12")
    
    # Fiscal year end
    fiscal_end = fiscal_start.replace(year=fiscal_start.year + 1) - timedelta(days=1)
    fiscal_end = fiscal_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return fiscal_start, fiscal_end


def get_iso_week_dates(
    year: int,
    week: int
) -> Tuple[date, date]:
    """
    Get the start and end dates of an ISO week.
    
    Args:
        year: Year
        week: ISO week number (1-53)
        
    Returns:
        Tuple of (week_start, week_end)
    """
    if not 1 <= week <= 53:
        raise ValueError("Week must be 1-53")
    
    # Get the Monday of the specified week
    jan1 = date(year, 1, 1)
    jan1_weekday = jan1.weekday()
    days_to_monday = (jan1_weekday - 1) % 7
    
    first_monday = jan1 - timedelta(days=days_to_monday)
    target_monday = first_monday + timedelta(weeks=week-1)
    
    # If the target Monday is before Jan 1, it's in the previous year
    if target_monday < jan1 and week > 1:
        raise ValueError(f"Week {week} is not valid for year {year}")
    
    # End of the week (Sunday)
    week_end = target_monday + timedelta(days=6)
    
    return target_monday, week_end


def is_dst_transition_ambiguous(
    dt: datetime,
    timezone_str: str
) -> bool:
    """
    Check if a datetime is ambiguous due to DST transition.
    
    Args:
        dt: Datetime to check
        timezone_str: Timezone
        
    Returns:
        True if ambiguous
    """
    tz = TimeZoneManager.get_timezone(timezone_str)
    
    if dt.tzinfo is not None:
        # Convert to naive in the specified timezone
        dt = dt.astimezone(tz).replace(tzinfo=None)
    
    try:
        return tz.localize(dt, is_dst=False) != tz.localize(dt, is_dst=True)
    except pytz.exceptions.AmbiguousTimeError:
        return True
    except pytz.exceptions.NonExistentTimeError:
        return False


def is_valid_iso8601(date_string: str) -> bool:
    """
    Check if a string is a valid ISO 8601 datetime.
    
    Args:
        date_string: String to check
        
    Returns:
        True if valid
    """
    try:
        iso8601.parse_date(date_string)
        return True
    except iso8601.ParseError:
        return False
    except ValueError:
        return False


def wait_until(target_time: datetime) -> None:
    """
    Wait until a specific time is reached.
    
    Args:
        target_time: Target time to wait for
    """
    if target_time.tzinfo is None:
        target_time = pytz.UTC.localize(target_time)
    
    now = utc_now()
    if now >= target_time:
        return
    
    sleep_seconds = (target_time - now).total_seconds()
    time.sleep(max(0, sleep_seconds))


# Default interval exports
intervals = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=30),  # Approximate
    "quarter": timedelta(days=91),  # Approximate
    "year": timedelta(days=365)  # Approximate
}