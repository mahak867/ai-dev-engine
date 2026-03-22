
const mongoose = require('mongoose');
const Schema = mongoose.Schema;
const investmentAmountSchema = new Schema({ amount: Number, date: Date });
const InvestmentAmountModel = mongoose.model('InvestmentAmount', investmentAmountSchema);
module.exports = InvestmentAmountModel;