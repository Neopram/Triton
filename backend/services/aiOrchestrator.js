// backend/services/aiOrchestrator.js
const axios = require('axios');
const { performance } = require('perf_hooks');
const crypto = require('crypto');
const cacheService = require('./cacheService');
const logger = require('../utils/logger');
const aiConfig = require('../config/aiConfig');

/**
 * AI Orchestrator Service
 * 
 * This service manages communication between the application and AI models.
 * It routes requests to either DeepSeek (cloud) or Phi-3 (local) based on:
 * - Task complexity
 * - Connection status
 * - Performance requirements
 */
class AIOrchestrator {
  constructor() {
    this.deepseekEndpoint = aiConfig.deepseek.endpoint;
    this.phi3Endpoint = aiConfig.phi3.endpoint;
    this.modelStatus = {
      deepseekAvailable: false,
      phi3Available: false,
      lastChecked: null
    };
    this.offlineMode = false;
    this.taskRouting = aiConfig.orchestration.taskRouting;
    
    // Initialize status check
    this._checkModelStatus();
    
    // Schedule periodic status checks
    setInterval(
      () => this._checkModelStatus(), 
      aiConfig.orchestration.healthCheckInterval
    );
  }
  
  /**
   * Check availability of both AI models
   * @private
   * @returns {Promise<Object>} Status of both models
   */
  async _checkModelStatus() {
    try {
      // Check DeepSeek availability
      const deepseekAvailable = await this._pingEndpoint(this.deepseekEndpoint);
      
      // Check Phi3 availability
      const phi3Available = await this._pingEndpoint(this.phi3Endpoint);
      
      // Update status
      this.modelStatus = {
        deepseekAvailable,
        phi3Available,
        lastChecked: new Date().toISOString()
      };
      
      // Update offline mode status
      if (!deepseekAvailable && !phi3Available) {
        if (!this.offlineMode) {
          logger.warn('All AI models unavailable - entering offline mode');
          this.offlineMode = true;
        }
      } else if (this.offlineMode) {
        logger.info('AI models now available - exiting offline mode');
        this.offlineMode = false;
      }
      
      // Log status changes
      if (!deepseekAvailable) {
        logger.warn('DeepSeek AI service unavailable');
      }
      if (!phi3Available) {
        logger.warn('Phi-3 AI service unavailable');
      }
      
      return this.modelStatus;
    } catch (error) {
      logger.error('Error checking AI model status:', error);
      return this.modelStatus;
    }
  }
  
  /**
   * Check if an endpoint is responding
   * @private
   * @param {string} endpoint API endpoint to ping
   * @returns {Promise<boolean>} Whether endpoint is available
   */
  async _pingEndpoint(endpoint) {
    try {
      const response = await axios.get(${endpoint}/health, { 
        timeout: 3000 // 3 second timeout
      });
      return response.status === 200;
    } catch (error) {
      return false;
    }
  }
  
  /**
   * Process a query through the appropriate AI model
   * @param {string} query User's query
   * @param {Object} context Additional context data
   * @param {string} taskType Type of task (maps to preferred model)
   * @returns {Promise<Object>} AI response with metadata
   */
  async processQuery(query, context = {}, taskType = 'basicQueries') {
    const startTime = performance.now();
    const queryId = this._generateQueryId(query, context, taskType);
    
    // Try to get from cache first
    if (aiConfig.orchestration.cacheEnabled) {
      const cachedResult = await cacheService.get(i_query:);
      if (cachedResult) {
        logger.debug(Cache hit for query: ...);
        
        return {
          result: cachedResult.result,
          source: 'cache',
          processingTime: performance.now() - startTime,
          queryId
        };
      }
    }
    
    // Determine which model to use
    const targetModel = this._determineTargetModel(taskType);
    
    // Process query with selected model
    try {
      let result;
      let source;
      
      if (targetModel === 'both') {
        // Process with both models and compare
        const results = await this._processBothModels(query, context);
        result = results.result;
        source = results.source;
      } else if (targetModel === 'deepseek') {
        // Process with DeepSeek
        result = await this._processWithDeepSeek(query, context);
        source = 'deepseek';
      } else if (targetModel === 'phi3') {
        // Process with Phi-3
        result = await this._processWithPhi3(query, context);
        source = 'phi3';
      } else {
        // Fallback to offline mode
        result = this._getOfflineResponse(query, taskType);
        source = 'offline';
      }
      
      const processingTime = performance.now() - startTime;
      
      // Cache the result if enabled
      if (aiConfig.orchestration.cacheEnabled && result) {
        await cacheService.set(i_query:, {
          result,
          timestamp: Date.now()
        }, aiConfig.orchestration.cacheTTL);
      }
      
      return {
        result,
        source,
        processingTime,
        queryId
      };
    } catch (error) {
      logger.error(AI processing error: );
      
      // Attempt fallback if primary model failed
      try {
        return await this._handleProcessingError(error, query, context, taskType, startTime);
      } catch (fallbackError) {
        logger.error(Fallback also failed: );
        throw new Error(AI processing failed: );
      }
    }
  }
  
  /**
   * Handle errors by trying fallback options
   * @private
   */
  async _handleProcessingError(error, query, context, taskType, startTime) {
    // Try alternative model
    const currentModel = this._determineTargetModel(taskType);
    const fallbackModel = currentModel === 'deepseek' ? 'phi3' : 'deepseek';
    
    logger.info(Trying fallback from  to );
    
    let result;
    let source;
    
    if (fallbackModel === 'deepseek' && this.modelStatus.deepseekAvailable) {
      result = await this._processWithDeepSeek(query, context);
      source = 'deepseek-fallback';
    } else if (fallbackModel === 'phi3' && this.modelStatus.phi3Available) {
      result = await this._processWithPhi3(query, context);
      source = 'phi3-fallback';
    } else {
      // No models available, use offline mode
      result = this._getOfflineResponse(query, taskType);
      source = 'offline-fallback';
    }
    
    const processingTime = performance.now() - startTime;
    
    return {
      result,
      source,
      processingTime,
      fallback: true
    };
  }
  
  /**
   * Determine which AI model to use based on task type and availability
   * @private
   * @param {string} taskType Type of task
   * @returns {string} Target model to use
   */
  _determineTargetModel(taskType) {
    // Get preferred model for this task type
    const preferredModel = this.taskRouting[taskType] || 'phi3';
    
    // If both models are unavailable, return offline
    if (!this.modelStatus.deepseekAvailable && !this.modelStatus.phi3Available) {
      return 'offline';
    }
    
    // If preferred model is available, use it
    if (preferredModel === 'deepseek' && this.modelStatus.deepseekAvailable) {
      return 'deepseek';
    }
    
    if (preferredModel === 'phi3' && this.modelStatus.phi3Available) {
      return 'phi3';
    }
    
    if (preferredModel === 'both') {
      // If both requested but only one available, use that one
      if (this.modelStatus.deepseekAvailable && !this.modelStatus.phi3Available) {
        return 'deepseek';
      }
      if (!this.modelStatus.deepseekAvailable && this.modelStatus.phi3Available) {
        return 'phi3';
      }
      if (this.modelStatus.deepseekAvailable && this.modelStatus.phi3Available) {
        return 'both';
      }
    }
    
    // Fallback to any available model
    if (this.modelStatus.phi3Available) {
      return 'phi3';
    }
    
    if (this.modelStatus.deepseekAvailable) {
      return 'deepseek';
    }
    
    // No models available
    return 'offline';
  }
  
  /**
   * Process query with DeepSeek
   * @private
   * @param {string} query User query
   * @param {Object} context Additional context
   * @returns {Promise<string>} AI response
   */
  async _processWithDeepSeek(query, context) {
    try {
      const payload = {
        prompt: this._formatDeepSeekPrompt(query, context),
        max_tokens: aiConfig.deepseek.maxTokens,
        temperature: aiConfig.deepseek.defaultTemperature,
        stream: false
      };
      
      const response = await axios.post(
        ${this.deepseekEndpoint}/generate, 
        payload, 
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': Bearer 
          },
          timeout: aiConfig.deepseek.requestTimeout
        }
      );
      
      return response.data.text;
    } catch (error) {
      logger.error(DeepSeek processing error: );
      throw error;
    }
  }
  
  /**
   * Process query with Phi-3
   * @private
   * @param {string} query User query
   * @param {Object} context Additional context
   * @returns {Promise<string>} AI response
   */
  async _processWithPhi3(query, context) {
    try {
      const payload = {
        input: query,
        max_length: aiConfig.phi3.maxTokens,
        temperature: aiConfig.phi3.defaultTemperature,
        maritime_context: context
      };
      
      const response = await axios.post(
        ${this.phi3Endpoint}/generate, 
        payload, 
        {
          headers: {
            'Content-Type': 'application/json'
          },
          timeout: aiConfig.phi3.requestTimeout
        }
      );
      
      return response.data.output;
    } catch (error) {
      logger.error(Phi-3 processing error: );
      throw error;
    }
  }
  
  /**
   * Process query with both models and compare results
   * @private
   * @param {string} query User query
   * @param {Object} context Additional context
   * @returns {Promise<Object>} Combined result
   */
  async _processBothModels(query, context) {
    try {
      // Run both models in parallel
      const [deepseekPromise, phi3Promise] = [
        this._processWithDeepSeek(query, context).catch(e => null),
        this._processWithPhi3(query, context).catch(e => null)
      ];
      
      const [deepseekResult, phi3Result] = await Promise.all([
        deepseekPromise,
        phi3Promise
      ]);
      
      // If one fails, return the other
      if (!deepseekResult) return { result: phi3Result, source: 'phi3-fallback' };
      if (!phi3Result) return { result: deepseekResult, source: 'deepseek-fallback' };
      
      // For critical tasks, we could implement consensus logic here
      // For now, prioritize DeepSeek for more complex tasks
      return { 
        result: deepseekResult, 
        source: 'consensus-deepseek' 
      };
    } catch (error) {
      logger.error(Error processing with both models: );
      throw error;
    }
  }
  
  /**
   * Format prompt for DeepSeek model
   * @private
   * @param {string} query User query
   * @param {Object} context Additional context
   * @returns {string} Formatted prompt
   */
  _formatDeepSeekPrompt(query, context) {
    let contextString = '';
    
    // Format vessel context if available
    if (context.vessel) {
      contextString += Current Vessel:  ()\n;
      contextString += Position: , \n;
      contextString += Status: \n;
      
      if (context.vessel.destination) {
        contextString += Destination: \n;
      }
      
      if (context.vessel.eta) {
        contextString += ETA: \n;
      }
    }
    
    // Format weather context if available
    if (context.weather) {
      contextString += \nWeather Conditions:\n;
      contextString += Description: \n;
      contextString += Wind:  kts at °\n;
      contextString += Sea State: \n;
      contextString += Visibility: \n;
    }
    
    // Add any other context
    if (context.additionalInfo) {
      contextString += \nAdditional Information:\n\n;
    }
    
    // Build final prompt
    return 
### System
You are Triton AI, a specialized maritime assistant for shipping and vessel management.
Provide expert, concise responses to maritime queries. Focus on accuracy and practical information.
For safety issues, emphasize maritime best practices and regulations.

### Context


### User Query


### Response
;
  }
  
  /**
   * Generate a consistent ID for a query (for caching)
   * @private
   * @param {string} query User query
   * @param {Object} context Context object
   * @param {string} taskType Task type
   * @returns {string} Unique query ID
   */
  _generateQueryId(query, context, taskType) {
    const data = {
      query,
      context: this._normalizeContext(context),
      taskType
    };
    
    const str = JSON.stringify(data);
    return crypto.createHash('md5').update(str).digest('hex');
  }
  
  /**
   * Normalize context object for consistent hashing
   * @private
   * @param {Object} context Original context
   * @returns {Object} Normalized context
   */
  _normalizeContext(context) {
    // Deep clone context to avoid modifications
    const normalized = JSON.parse(JSON.stringify(context));
    
    // Remove or normalize volatile fields that shouldn't affect caching
    if (normalized.timestamp) delete normalized.timestamp;
    if (normalized.requestId) delete normalized.requestId;
    
    return normalized;
  }
  
  /**
   * Get offline response when no AI models are available
   * @private
   * @param {string} query User query
   * @param {string} taskType Task type
   * @returns {string} Offline response
   */
  _getOfflineResponse(query, taskType) {
    // Basic responses for offline mode
    const responses = {
      vesselTracking: "Vessel tracking data is not available in offline mode. Please try again when online connectivity is restored.",
      weatherAnalysis: "Weather analysis is not available in offline mode. Basic cached weather data may be available in your local system.",
      routeOptimization: "Route optimization requires online connectivity to process complex maritime data. Please try again when connection is restored.",
      basicQueries: "I'm currently in offline mode with limited functionality. I can provide basic information, but real-time data and advanced analysis require online connectivity.",
      default: "I'm currently operating in offline mode with limited capabilities. Please check your internet connection and try again later."
    };
    
    return responses[taskType] || responses.default;
  }
  
  /**
   * Get current status of AI services
   * @returns {Object} Status information
   */
  getStatus() {
    return {
      deepseek: this.modelStatus.deepseekAvailable ? 'online' : 'offline',
      phi3: this.modelStatus.phi3Available ? 'online' : 'offline',
      mode: this.offlineMode ? 'offline' : 'online',
      lastChecked: this.modelStatus.lastChecked,
      endpoints: {
        deepseek: this.deepseekEndpoint,
        phi3: this.phi3Endpoint
      }
    };
  }
}

// Export singleton instance
module.exports = new AIOrchestrator();
