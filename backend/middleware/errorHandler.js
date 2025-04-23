// backend/middleware/errorHandler.js
const logger = require('../utils/logger');

/**
 * Global error handling middleware
 */
const errorHandler = (err, req, res, next) => {
  // Log error details
  logger.error(Error: );
  logger.debug(err.stack);
  
  // Default error status and message
  let statusCode = err.statusCode || 500;
  let message = err.message || 'Internal Server Error';
  
  // Handle specific error types
  if (err.name === 'ValidationError') {
    statusCode = 400;
    message = Object.values(err.errors).map(val => val.message).join(', ');
  }
  
  if (err.name === 'CastError') {
    statusCode = 400;
    message = Invalid : ;
  }
  
  if (err.code === 11000) {
    statusCode = 400;
    message = Duplicate value for  field;
  }
  
  // Database connection errors
  if (err.name === 'MongoError' || err.name === 'SequelizeConnectionError') {
    statusCode = 503;
    message = 'Database service unavailable';
  }
  
  // Send response
  res.status(statusCode).json({
    success: false,
    message,
    // Include stack trace in development, not in production
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
};

module.exports = errorHandler;
