// backend/server.js
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const path = require('path');
require('dotenv').config();

// Import routes
const vesselRoutes = require('./routes/vesselRoutes');
const portRoutes = require('./routes/portRoutes');
const userRoutes = require('./routes/userRoutes');
const weatherRoutes = require('./routes/weatherRoutes');
const aiRoutes = require('./routes/aiRoutes');

// Import middleware
const { authenticateJWT } = require('./middleware/auth');
const errorHandler = require('./middleware/errorHandler');

// Initialize app
const app = express();
const PORT = process.env.PORT || 5000;

// Security and utility middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(morgan('dev'));

// Set up routes
app.use('/api/users', userRoutes);
app.use('/api/vessels', authenticateJWT, vesselRoutes);
app.use('/api/ports', authenticateJWT, portRoutes);
app.use('/api/weather', authenticateJWT, weatherRoutes);
app.use('/api/ai', authenticateJWT, aiRoutes);

// Serve static frontend in production
if (process.env.NODE_ENV === 'production') {
  app.use(express.static(path.join(__dirname, '../frontend/build')));
  
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../frontend/build', 'index.html'));
  });
}

// Error handling middleware
app.use(errorHandler);

// Start server
app.listen(PORT, () => {
  console.log(Triton API server running on port );
});

module.exports = app; // Export for testing
