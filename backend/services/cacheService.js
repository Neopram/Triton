// backend/services/cacheService.js
const Redis = require('ioredis');
const logger = require('../utils/logger');

/**
 * Cache service using Redis for storing frequently accessed data
 * and AI responses to improve performance
 */
class CacheService {
  constructor() {
    this.isConnected = false;
    this.redisEnabled = process.env.CACHE_ENABLED !== 'false';
    
    if (this.redisEnabled) {
      try {
        // Connect to Redis
        this.redis = new Redis({
          host: process.env.REDIS_HOST || 'localhost',
          port: process.env.REDIS_PORT || 6379,
          password: process.env.REDIS_PASSWORD || '',
          retryStrategy: (times) => {
            const delay = Math.min(times * 50, 2000);
            return delay;
          }
        });
        
        this.redis.on('connect', () => {
          logger.info('Cache service connected to Redis');
          this.isConnected = true;
        });
        
        this.redis.on('error', (err) => {
          logger.error(Cache service Redis error: );
          this.isConnected = false;
        });
      } catch (error) {
        logger.error(Failed to initialize Redis cache: );
        this.redis = null;
        this.isConnected = false;
      }
    } else {
      logger.info('Cache service disabled via configuration');
      this.redis = null;
    }
    
    // Fallback to in-memory cache if Redis is not available
    this.memoryCache = new Map();
    this.memoryCacheExpiry = new Map();
  }
  
  /**
   * Store data in cache
   * @param {string} key - Cache key
   * @param {any} data - Data to store
   * @param {number} ttl - Time to live in seconds
   * @returns {Promise<boolean>} - Success status
   */
  async set(key, data, ttl = 3600) {
    try {
      // Serialize data to JSON
      const serialized = JSON.stringify(data);
      
      if (this.isConnected && this.redis) {
        // Store in Redis with expiration
        await this.redis.setex(key, ttl, serialized);
      } else {
        // Fallback to in-memory cache
        this.memoryCache.set(key, serialized);
        
        // Set expiry timestamp
        const expiryTime = Date.now() + (ttl * 1000);
        this.memoryCacheExpiry.set(key, expiryTime);
        
        // Clean up expired items periodically
        if (this.memoryCache.size % 10 === 0) {
          this._cleanupMemoryCache();
        }
      }
      
      return true;
    } catch (error) {
      logger.error(Cache set error: );
      return false;
    }
  }
  
  /**
   * Retrieve data from cache
   * @param {string} key - Cache key
   * @returns {Promise<any>} - Retrieved data or null if not found
   */
  async get(key) {
    try {
      let serialized = null;
      
      if (this.isConnected && this.redis) {
        // Get from Redis
        serialized = await this.redis.get(key);
      } else {
        // Check in-memory cache
        if (this.memoryCache.has(key)) {
          // Check if expired
          const expiry = this.memoryCacheExpiry.get(key);
          if (expiry && expiry > Date.now()) {
            serialized = this.memoryCache.get(key);
          } else {
            // Remove expired item
            this.memoryCache.delete(key);
            this.memoryCacheExpiry.delete(key);
          }
        }
      }
      
      // Return null if not found
      if (!serialized) {
        return null;
      }
      
      // Parse and return data
      return JSON.parse(serialized);
    } catch (error) {
      logger.error(Cache get error: );
      return null;
    }
  }
  
  /**
   * Delete an item from cache
   * @param {string} key - Cache key
   * @returns {Promise<boolean>} - Success status
   */
  async del(key) {
    try {
      if (this.isConnected && this.redis) {
        await this.redis.del(key);
      } else {
        this.memoryCache.delete(key);
        this.memoryCacheExpiry.delete(key);
      }
      
      return true;
    } catch (error) {
      logger.error(Cache delete error: );
      return false;
    }
  }
  
  /**
   * Clear all cache
   * @returns {Promise<boolean>} - Success status
   */
  async clear() {
    try {
      if (this.isConnected && this.redis) {
        await this.redis.flushall();
      } else {
        this.memoryCache.clear();
        this.memoryCacheExpiry.clear();
      }
      
      return true;
    } catch (error) {
      logger.error(Cache clear error: );
      return false;
    }
  }
  
  /**
   * Clean up expired items from memory cache
   * @private
   */
  _cleanupMemoryCache() {
    const now = Date.now();
    
    for (const [key, expiry] of this.memoryCacheExpiry.entries()) {
      if (expiry < now) {
        this.memoryCache.delete(key);
        this.memoryCacheExpiry.delete(key);
      }
    }
  }
}

// Export singleton instance
module.exports = new CacheService();
