// backend/config/aiConfig.js

/**
 * Configuration for AI services
 */
const aiConfig = {
  // DeepSeek (cloud) configuration
  deepseek: {
    endpoint: process.env.DEEPSEEK_API_ENDPOINT || 'http://localhost:8000',
    apiKey: process.env.DEEPSEEK_API_KEY,
    defaultModel: 'deepseek-coder-33b-instruct',
    requestTimeout: 30000, // 30 seconds
    maxTokens: 2048,
    defaultTemperature: 0.7
  },
  
  // Phi-3 (local) configuration
  phi3: {
    endpoint: process.env.PHI3_API_ENDPOINT || 'http://localhost:8001',
    requestTimeout: 15000, // 15 seconds
    maxTokens: 1024,
    defaultTemperature: 0.5
  },
  
  // Orchestration settings
  orchestration: {
    // Task routing preferences (which AI to use for which task)
    taskRouting: {
      routeOptimization: 'deepseek',
      complexAnalysis: 'deepseek',
      weatherAnalysis: 'deepseek',
      vesselTracking: 'phi3',
      basicQueries: 'phi3',
      portOperations: 'phi3',
      criticalSafety: 'both'  // Run on both models
    },
    
    // Fallback strategy
    fallbackPriority: ['phi3', 'deepseek', 'cached', 'offline'],
    
    // Cache settings
    cacheEnabled: true,
    cacheTTL: 3600,  // Cache lifetime in seconds
    
    // Health check interval
    healthCheckInterval: 60000  // 1 minute
  },
  
  // Retry settings
  retryStrategy: {
    maxRetries: 3,
    initialDelay: 1000,  // 1 second
    maxDelay: 10000,     // 10 seconds
    factor: 2            // Exponential backoff factor
  }
};

module.exports = aiConfig;
