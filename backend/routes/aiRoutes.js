// backend/routes/aiRoutes.js
const express = require('express');
const aiController = require('../controllers/aiController');
const { authorizeRoles } = require('../middleware/auth');

const router = express.Router();

/**
 * @route   POST /api/ai/query
 * @desc    Process an AI query
 * @access  Private
 */
router.post('/query', aiController.processQuery);

/**
 * @route   GET /api/ai/status
 * @desc    Get AI service status
 * @access  Private
 */
router.get('/status', aiController.getStatus);

/**
 * @route   POST /api/ai/optimize-route
 * @desc    Optimize a maritime route
 * @access  Private
 */
router.post('/optimize-route', aiController.optimizeRoute);

/**
 * @route   POST /api/ai/analyze-weather
 * @desc    Analyze weather implications
 * @access  Private
 */
router.post('/analyze-weather', aiController.analyzeWeather);

/**
 * @route   POST /api/ai/predict-eta
 * @desc    Predict estimated time of arrival
 * @access  Private
 */
router.post('/predict-eta', aiController.predictEta);

/**
 * @route   POST /api/ai/feedback
 * @desc    Submit feedback on AI response
 * @access  Private
 */
router.post('/feedback', aiController.submitFeedback);

/**
 * @route   GET /api/ai/settings
 * @desc    Get AI settings
 * @access  Private
 */
router.get('/settings', aiController.getSettings);

/**
 * @route   PUT /api/ai/settings
 * @desc    Update AI settings
 * @access  Private (Admin only)
 */
router.put('/settings', authorizeRoles(['admin']), aiController.updateSettings);

module.exports = router;
