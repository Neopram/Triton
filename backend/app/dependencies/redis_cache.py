import json
import pickle
from typing import Any, Optional, TypeVar, Generic, Callable, Union
import redis.asyncio as redis
from fastapi import Depends
from app.core.config import settings
from app.core.logging import db_logger

# Type variable for generic cache
T = TypeVar('T')

# Redis connection pool
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL, 
    decode_responses=True,
    max_connections=settings.REDIS_MAX_CONNECTIONS
)


class RedisCache(Generic[T]):
    """Redis cache wrapper with typed operations"""
    
    def __init__(self, prefix: str = "cache"):
        """
        Initialize Redis cache with a prefix for keys
        
        Args:
            prefix: Prefix for all keys in this cache instance
        """
        self.prefix = prefix
        self.redis = redis.Redis(connection_pool=redis_pool)
    
    def _get_key(self, key: str) -> str:
        """Get prefixed key"""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """
        Get a value from cache
        
        Args:
            key: Cache key
            default: Default value if key doesn't exist
            
        Returns:
            Cached value or default
        """
        full_key = self._get_key(key)
        try:
            value = await self.redis.get(full_key)
            if value is None:
                return default
            
            try:
                # Try to parse as JSON first
                return json.loads(value)
            except json.JSONDecodeError:
                # If not JSON, try pickle
                return pickle.loads(value)
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis get error: {str(e)}",
                {"key": full_key}
            )
            return default
    
    async def set(
        self, 
        key: str, 
        value: T, 
        expire: Optional[int] = None
    ) -> bool:
        """
        Set a value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds
            
        Returns:
            True if successful
        """
        full_key = self._get_key(key)
        try:
            # Try to serialize as JSON
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                # If not JSON serializable, use pickle
                serialized = pickle.dumps(value)
            
            await self.redis.set(full_key, serialized, ex=expire)
            return True
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis set error: {str(e)}",
                {"key": full_key}
            )
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted
        """
        full_key = self._get_key(key)
        try:
            return bool(await self.redis.delete(full_key))
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis delete error: {str(e)}",
                {"key": full_key}
            )
            return False
    
    async def clear_prefix(self) -> bool:
        """
        Clear all keys with this cache's prefix
        
        Returns:
            True if successful
        """
        try:
            cursor = 0
            pattern = f"{self.prefix}:*"
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis clear_prefix error: {str(e)}",
                {"prefix": self.prefix}
            )
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists
        """
        full_key = self._get_key(key)
        try:
            return bool(await self.redis.exists(full_key))
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis exists error: {str(e)}",
                {"key": full_key}
            )
            return False
    
    async def get_or_set(
        self, 
        key: str, 
        default_factory: Callable[[], Union[T, Any]], 
        expire: Optional[int] = None
    ) -> T:
        """
        Get a value from cache or set it if it doesn't exist
        
        Args:
            key: Cache key
            default_factory: Function to call to get default value
            expire: Expiration time in seconds
            
        Returns:
            Cached value or newly set value
        """
        full_key = self._get_key(key)
        try:
            # Check if key exists
            if await self.exists(key):
                return await self.get(key)
            
            # Get default value and set it
            value = default_factory()
            await self.set(key, value, expire=expire)
            return value
        except Exception as e:
            db_logger.structured(
                "error",
                f"Redis get_or_set error: {str(e)}",
                {"key": full_key}
            )
            # If cache fails, just return the computed value
            return default_factory()


# Create cache instances for different types of data
market_cache = RedisCache[dict]("market")
vessel_cache = RedisCache[dict]("vessel")
voyage_cache = RedisCache[dict]("voyage")
user_cache = RedisCache[dict]("user")
insight_cache = RedisCache[dict]("insight")


def get_market_cache():
    """Dependency for market cache"""
    return market_cache


def get_vessel_cache():
    """Dependency for vessel cache"""
    return vessel_cache


def get_voyage_cache():
    """Dependency for voyage cache"""
    return voyage_cache


def get_user_cache():
    """Dependency for user cache"""
    return user_cache


def get_insight_cache():
    """Dependency for insight cache"""
    return insight_cache