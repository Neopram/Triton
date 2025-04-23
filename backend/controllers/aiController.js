// backend/controllers/aiController.js
const aiOrchestrator = require('../services/aiOrchestrator');
const logger = require('../utils/logger');
const aiConfig = require('../config/aiConfig');

/**
 * AI Controller
 * Handles API requests related to AI functionality
 */
const aiController = {
  /**
   * Process a general AI query
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  processQuery: async (req, res) => {
    try {
      const { query, context, taskType } = req.body;
      
      // Validate required fields
      if (!query) {
        return res.status(400).json({
          success: false,
          message: 'Query is required'
        });
      }
      
      // Add user info to context
      const enhancedContext = {
        ...context,
        user: {
          id: req.user.id,
          role: req.user.role
        }
      };
      
      // Process the query
      const result = await aiOrchestrator.processQuery(
        query, 
        enhancedContext, 
        taskType || 'basicQueries'
      );
      
      return res.status(200).json({
        success: true,
        data: result
      });
    } catch (error) {
      logger.error(AI query processing error: );
      return res.status(500).json({
        success: false,
        message: 'Error processing AI query',
        error: error.message
      });
    }
  },
  
  /**
   * Get AI service status
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  getStatus: async (req, res) => {
    try {
      const status = aiOrchestrator.getStatus();
      
      return res.status(200).json({
        success: true,
        data: status
      });
    } catch (error) {
      logger.error(Error getting AI status: );
      return res.status(500).json({
        success: false,
        message: 'Error retrieving AI status',
        error: error.message
      });
    }
  },
  
  /**
   * Optimize a maritime route using AI
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  optimizeRoute: async (req, res) => {
    try {
      const {
        vesselId,
        origin,
        destination,
        departureTime,
        constraints = {},
        preferences = {}
      } = req.body;
      
      // Validate required fields
      if (!vesselId || !origin || !destination) {
        return res.status(400).json({
          success: false,
          message: 'Vessel ID, origin, and destination are required'
        });
      }
      
      // Format query for route optimization
      const query = Optimize route from  to  considering all maritime factors;
      
      // Build context
      const context = {
        taskType: 'routeOptimization',
        vessel: { id: vesselId },
        origin,
        destination,
        departureTime,
        constraints,
        preferences
      };
      
      // Process with AI orchestrator
      const result = await aiOrchestrator.processQuery(
        query, 
        context, 
        'routeOptimization'
      );
      
      // Format results
      return res.status(200).json({
        success: true,
        data: {
          optimizedRoute: result.result,
          source: result.source,
          processingTime: result.processingTime
        }
      });
    } catch (error) {
      logger.error(Route optimization error: );
      return res.status(500).json({
        success: false,
        message: 'Error optimizing route',
        error: error.message
      });
    }
  },
  
  /**
   * Analyze weather implications on maritime operations
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  analyzeWeather: async (req, res) => {
    try {
      const { vesselId, route, weatherData } = req.body;
      
      // Validate required fields
      if (!weatherData) {
        return res.status(400).json({
          success: false,
          message: 'Weather data is required'
        });
      }
      
      // Format query for weather analysis
      const query = 'Analyze the impact of current and forecasted weather on maritime operations';
      
      // Build context
      const context = {
        taskType: 'weatherAnalysis',
        vessel: vesselId ? { id: vesselId } : null,
        route,
        weather: weatherData
      };
      
      // Process with AI orchestrator
      const result = await aiOrchestrator.processQuery(
        query, 
        context, 
        'weatherAnalysis'
      );
      
      return res.status(200).json({
        success: true,
        data: {
          analysis: result.result,
          source: result.source,
          processingTime: result.processingTime
        }
      });
    } catch (error) {
      logger.error(Weather analysis error: );
      return res.status(500).json({
        success: false,
        message: 'Error analyzing weather implications',
        error: error.message
      });
    }
  },
  
  /**
   * Predict estimated time of arrival
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  predictEta: async (req, res) => {
    try {
      const { vesselId, origin, destination, speed, weatherData } = req.body;
      
      // Validate required fields
      if (!vesselId || !origin || !destination) {
        return res.status(400).json({
          success: false,
          message: 'Vessel ID, origin, and destination are required'
        });
      }
      
      // Format query for ETA prediction
      const query = Predict ETA for vessel traveling from  to ;
      
      // Build context
      const context = {
        taskType: 'etaPrediction',
        vessel: { id: vesselId, speed },
        origin,
        destination,
        weather: weatherData
      };
      
      // Process with AI orchestrator
      const result = await aiOrchestrator.processQuery(
        query, 
        context, 
        'etaPrediction'
      );
      
      return res.status(200).json({
        success: true,
        data: {
          eta: result.result,
          source: result.source,
          processingTime: result.processingTime
        }
      });
    } catch (error) {
      logger.error(ETA prediction error: );
      return res.status(500).json({
        success: false,
        message: 'Error predicting ETA',
        error: error.message
      });
    }
  },
  
  /**
   * Submit feedback on AI response
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  submitFeedback: async (req, res) => {
    try {
      const { queryId, rating, feedback, originalQuery, aiResponse } = req.body;
      
      // Validate required fields
      if (!queryId || !rating) {
        return res.status(400).json({
          success: false,
          message: 'Query ID and rating are required'
        });
      }
      
      // Store feedback for model improvement (implementation depends on your storage)
      logger.info(AI feedback received: , Rating: );
      
      // You would typically store this in a database
      
      return res.status(200).json({
        success: true,
        message: 'Feedback submitted successfully'
      });
    } catch (error) {
      logger.error(Feedback submission error: );
      return res.status(500).json({
        success: false,
        message: 'Error submitting feedback',
        error: error.message
      });
    }
  },
  
  /**
   * Get AI settings
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  getSettings: async (req, res) => {
    try {
      // Return current AI settings
      // Removing sensitive information
      const settings = {
        deepseek: {
          enabled: true,
          endpoint: aiConfig.deepseek.endpoint,
          defaultModel: aiConfig.deepseek.defaultModel,
          defaultTemperature: aiConfig.deepseek.defaultTemperature
        },
        phi3: {
          enabled: true,
          endpoint: aiConfig.phi3.endpoint,
          defaultTemperature: aiConfig.phi3.defaultTemperature
        },
        orchestration: {
          taskRouting: aiConfig.orchestration.taskRouting,
          cacheEnabled: aiConfig.orchestration.cacheEnabled,
          cacheTTL: aiConfig.orchestration.cacheTTL
        }
      };
      
      return res.status(200).json({
        success: true,
        data: settings
      });
    } catch (error) {
      logger.error(Error getting AI settings: );
      return res.status(500).json({
        success: false,
        message: 'Error retrieving AI settings',
        error: error.message
      });
    }
  },
  
  /**
   * Update AI settings (admin only)
   * @param {Object} req - Express request object
   * @param {Object} res - Express response object
   */
  updateSettings: async (req, res) => {
    try {
      const { settings } = req.body;
      
      // Validate settings object
      if (!settings || typeof settings !== 'object') {
        return res.status(400).json({
          success: false,
          message: 'Valid settings object is required'
        });
      }
      
      // In a real implementation, you would update configuration in database
      // and possibly restart the services
      
      logger.info(AI settings updated by admin: );
      
      return res.status(200).json({
        success: true,
        message: 'Settings updated successfully'
      });
    } catch (error) {
      logger.error(Error updating AI settings: );
      return res.status(500).json({
        success: false,
        message: 'Error updating AI settings',
        error: error.message
      });
    }
  }
};

module.exports = aiController;
