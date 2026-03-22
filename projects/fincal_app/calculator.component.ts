
import React, { useState } from 'react';
interface SIPCalculationState {
    investmentAmount: number;
    interestRate: number;
    years: number;
}
const CalculatorComponent = () => {
    const [state, setState] = useState<SIPCalculationState>({
        investmentAmount: 0,
        interestRate: 0,
        years: 0
    });
    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>, field: 'investmentAmount' | 'interestRate' | 'years') => {
        setState({ ...state, [field]: parseFloat(event.target.value) });
    };
    const calculateTotalAmount = () => {
        // TO DO: implement SIP calculation logic
    };
    return (
        <div>
            <h2>Financial Calculator</h2>
            <form onSubmit={(event) => {}}>
                <label>Investment Amount:</label>
                <input type="number" value={state.investmentAmount} onChange={(event) => handleInputChange(event, 'investmentAmount')} />
                <br />
                <label>Interest Rate:</label>
                <input type="number" value={state.interestRate} onChange={(event) => handleInputChange(event, 'interestRate')} />
                <br />
                <label>Years:</label>
                <input type="number" value={state.years} onChange={(event) => handleInputChange(event, 'years')} />
                <br />
                <button onClick={() => console.log('Calculator Component: SIP Calculation State:', state)}>Calculate</button>
            </form>
        </div>
    );
};
export default CalculatorComponent;