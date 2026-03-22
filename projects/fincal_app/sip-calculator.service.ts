
import { Injectable } from '@angular/core';
@Injectable({ providedIn: 'root' })
class SipCalculatorService {
    constructor(private state: SIPCalculationState) {}
    calculateTotalAmount(): number {
        const investmentAmount = this.state.investmentAmount;
        const interestRate = this.state.interestRate / 100;
        const years = this.state.years;
        let totalAmount = investmentAmount;
        for (let i = 0; i < years; i++) {
            totalAmount += (totalAmount * interestRate);
        }
        return totalAmount;
    }
}
export default SipCalculatorService;