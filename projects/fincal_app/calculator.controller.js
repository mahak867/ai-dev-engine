
const express = require('express');
const router = express.Router();
router.get('/sip-calculator', (req, res) => {
    const state = { investmentAmount: 0, interestRate: 0, years: 0 };
    // TO DO: implement SIP calculation logic
    res.json(state);
});
module.exports = router;