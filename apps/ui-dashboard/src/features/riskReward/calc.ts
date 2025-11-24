export type ScenarioOutcome = "LOSING" | "BREAKEVEN" | "PROFITABLE";

export interface Scenario {
  id: string; // e.g. "L1", "P2"
  label: string; // e.g. "Loss Scenario 1"
  rewardMultiple: number; // R (Risk:Reward), e.g. 1.10 means 1 Risk : 1.10 Reward
  expectancyR: number; // expectancy in R units (net of costs)
  expectancyPerTrade: number; // dollars per trade (net of costs)
  expectancyOverNTrades: number; // dollars over numTrades
  updatedCapital: number; // capital + expectancyOverNTrades (min 0)
  percentChange: number; // (updatedCapital - capital) / capital
  approxTradesToZero?: number; // only for losing scenarios
  outcome: ScenarioOutcome;
}

export interface RiskRewardInput {
  capital: number; // starting capital, e.g. 4000
  winRatePct: number; // e.g. 57.77
  riskPerTrade: number; // in dollars, e.g. 400
  slippagePct: number; // % of risk per trade, e.g. 0.42
  commissionPct: number; // % of risk per trade, e.g. 5
  numTrades: number; // e.g. 100
}

export interface RiskRewardResult {
  rBreakEven: number; // net break-even R (Risk:Reward)
  costPerTrade: number; // in dollars
  lossScenarios: Scenario[];
  breakEvenScenarios: Scenario[];
  profitScenarios: Scenario[];
}

/**
 * Build risk/reward scenarios based on input parameters
 */
export function buildRiskRewardScenarios(
  input: RiskRewardInput
): RiskRewardResult {
  const {
    capital,
    winRatePct,
    riskPerTrade,
    slippagePct,
    commissionPct,
    numTrades,
  } = input;

  // Convert win rate to decimal
  const W = winRatePct / 100;

  // Validate inputs
  if (W <= 0 || W >= 1) {
    throw new Error("Win rate must be between 0 and 100 (exclusive).");
  }

  if (riskPerTrade <= 0) {
    throw new Error("Risk per trade must be positive.");
  }

  const riskDollar = riskPerTrade;

  // Calculate cost per trade (slippage + commission as % of risk)
  const costPerTrade = (riskDollar * (slippagePct + commissionPct)) / 100;

  // Compute break-even R:R INCLUDING costs
  // E$ = W * (R * risk - C) + (1 - W) * (-risk - C) = 0
  // => W * R * risk - W * C - (1 - W) * risk - (1 - W) * C = 0
  // => W * R * risk - risk + W * risk - C = 0
  // => risk * (W * R - 1 + W) = C
  // => W * R = 1 - W + C / risk
  // => R_BE = (1 - W + C / risk) / W
  const rBreakEven = (1 - W + costPerTrade / riskDollar) / W;

  // Create loss scenarios (below break-even)
  // Generate scenarios from 0.7 R up to 0.98 * rBreakEven to get close to break-even
  // Minimum R value is 0.7 (don't go below 0.7 Reward)
  const lossRValues: number[] = [];
  
  // Start from 0.7 (minimum) or break-even * 0.7, whichever is higher
  // But ensure we don't go below 0.7
  const minRR = Math.max(0.7, Math.min(0.7 * rBreakEven, rBreakEven * 0.7));
  const maxRR = rBreakEven * 0.98; // Go up to 98% of break-even
  
  // Only generate scenarios if minRR is less than maxRR and both are below break-even
  if (minRR < maxRR && minRR < rBreakEven) {
    // Generate approximately 8-10 scenarios between min and max
    const numScenarios = 9;
    const stepSize = (maxRR - minRR) / (numScenarios - 1);
    
    for (let i = 0; i < numScenarios; i++) {
      const rr = minRR + (stepSize * i);
      const roundedRR = Math.round(rr * 100) / 100;
      // Only add if it's below break-even and >= 0.7
      if (roundedRR < rBreakEven && roundedRR >= 0.7) {
        lossRValues.push(roundedRR);
      }
    }
  }
  
  // Ensure we don't exceed break-even and don't go below 0.7
  const filteredLossRValues = lossRValues.filter(
    rr => rr < rBreakEven && rr >= 0.7
  );
  
  // If we filtered out too many, add some standard ones (but ensure >= 0.7)
  if (filteredLossRValues.length < 3) {
    filteredLossRValues.length = 0;
    // Generate scenarios from 0.7 up to break-even
    const standardMultipliers = [0.7, 0.75, 0.8, 0.85, 0.9, 0.95];
    for (const mult of standardMultipliers) {
      const rr = Math.round(rBreakEven * mult * 100) / 100;
      if (rr < rBreakEven && rr >= 0.7) {
        filteredLossRValues.push(rr);
      }
    }
  }
  
  // Ensure minimum is 0.7
  if (filteredLossRValues.length > 0 && filteredLossRValues[0] < 0.7) {
    filteredLossRValues[0] = 0.7;
  }
  
  // Use the filtered values
  lossRValues.length = 0;
  lossRValues.push(...filteredLossRValues);

  // Create profit scenarios
  // First scenario: break-even + 0.15
  // Then increment by 0.15 up to 1.0
  // Then increment by 0.10 from 1.0 up to at least 2.0
  const profitRValues: number[] = [];
  
  // Start at break-even + 0.15
  let currentRR = Math.round((rBreakEven + 0.15) * 100) / 100;
  
  // If break-even + 0.15 is already >= 1.0, start from there
  if (currentRR >= 1.0) {
    // If we're already at or above 1.0, add it and then increment by 0.10
    if (currentRR > 1.0) {
      profitRValues.push(1.0);
      currentRR = 1.1;
    } else {
      profitRValues.push(1.0);
      currentRR = 1.1;
    }
  } else {
    // Increment by 0.15 until we reach or exceed 1.0
    while (currentRR < 1.0) {
      profitRValues.push(currentRR);
      currentRR = Math.round((currentRR + 0.15) * 100) / 100;
      if (currentRR >= 1.0) {
        // Add 1.0 if we haven't already
        if (profitRValues.length === 0 || profitRValues[profitRValues.length - 1] < 1.0) {
          profitRValues.push(1.0);
        }
        currentRR = 1.1;
        break;
      }
    }
  }
  
  // Now increment by 0.10 from 1.1 up to at least 2.0
  while (currentRR <= 2.0) {
    profitRValues.push(currentRR);
    currentRR = Math.round((currentRR + 0.1) * 100) / 100;
  }
  
  // Ensure we always have at least one scenario and always include 2.0
  if (profitRValues.length === 0) {
    profitRValues.push(Math.min(1.0, rBreakEven + 0.15));
  }
  
  // Ensure 2.0 is always included if it's not already there
  if (profitRValues[profitRValues.length - 1] < 2.0) {
    profitRValues.push(2.0);
  }

  // Helper function to create a scenario
  const createScenario = (
    id: string,
    label: string,
    R: number
  ): Scenario => {
    // R = Risk:Reward multiple (1 Risk : R Reward)
    const grossWin = R * riskDollar; // before costs
    const grossLoss = -riskDollar; // before costs

    const netWin = grossWin - costPerTrade;
    const netLoss = grossLoss - costPerTrade;

    // Expectancy in dollars per trade
    const expectancyPerTrade = W * netWin + (1 - W) * netLoss;

    // Expectancy in R
    const expectancyR = expectancyPerTrade / riskDollar;

    // Expectancy over N trades
    const expectancyOverNTrades = expectancyPerTrade * numTrades;

    // Updated capital (can be negative for loss scenarios)
    const updatedCapital = capital + expectancyOverNTrades;

    // Percent change
    const percentChange = (updatedCapital - capital) / capital;

    // Approximate trades to zero (only for losing expectancy)
    let approxTradesToZero: number | undefined;
    if (expectancyPerTrade < 0) {
      approxTradesToZero = Math.floor(
        capital / Math.abs(expectancyPerTrade)
      );
    }

    // Determine outcome
    let outcome: ScenarioOutcome;
    if (Math.abs(expectancyR) < 1e-6) {
      outcome = "BREAKEVEN";
    } else if (expectancyR > 0) {
      outcome = "PROFITABLE";
    } else {
      outcome = "LOSING";
    }

    return {
      id,
      label,
      rewardMultiple: R,
      expectancyR,
      expectancyPerTrade,
      expectancyOverNTrades,
      updatedCapital,
      percentChange,
      approxTradesToZero,
      outcome,
    };
  };

  // Generate loss scenarios
  const lossScenarios: Scenario[] = lossRValues.map((R, index) =>
    createScenario(`L${index + 1}`, `Loss Scenario ${index + 1}`, R)
  );

  // Generate break-even scenario (exactly at break-even)
  const breakEvenScenario = createScenario("BE1", "Break-even Scenario", rBreakEven);
  const breakEvenScenarios: Scenario[] = [breakEvenScenario];

  // Generate profit scenarios and filter to only show positive ones
  const allProfitScenarios: Scenario[] = profitRValues.map((R, index) =>
    createScenario(`P${index + 1}`, `Profit Scenario ${index + 1}`, R)
  );
  
  // Filter to only show scenarios with positive expectancy (PROFITABLE outcome)
  const profitScenarios: Scenario[] = allProfitScenarios.filter(
    (scenario) => scenario.outcome === "PROFITABLE" && scenario.expectancyR > 0
  );

  return {
    rBreakEven,
    costPerTrade,
    lossScenarios,
    breakEvenScenarios,
    profitScenarios,
  };
}
