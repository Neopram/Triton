// Placeholder route file
const express = require('express');
const router = express.Router();

router.get('/', (req, res) => {
    res.json({ message: 'Route placeholder' });
});

module.exports = router;
