export type ScenarioOutcome = "LOSING" | "BREAKEVEN" | "PROFITABLE";

export interface Scenario {
  id: string; // e.g. "L1", "P2"
  label: string; // e.g. "Loss Scenario 1"
  rewardMultiple: number; // R (Reward:Risk), e.g. 1.10
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
  rBreakEven: number; // net break-even R (Reward:Risk)
  costPerTrade: number; // in dollars
  lossScenarios: Scenario[];
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
  const lossRValues = [
    0.5 * rBreakEven, // L1
    0.75 * rBreakEven, // L2
    0.9 * rBreakEven, // L3
  ];

  // Create profit scenarios
  // First scenario: break-even + 0.15
  // Then increment by 0.15 up to 1.0
  // Then increment by 0.10 from 1.0 up to 1.7
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
  
  // Now increment by 0.10 from 1.1 up to 1.7
  while (currentRR <= 1.7) {
    profitRValues.push(currentRR);
    currentRR = Math.round((currentRR + 0.1) * 100) / 100;
  }
  
  // Ensure we always have at least one scenario
  if (profitRValues.length === 0) {
    profitRValues.push(Math.min(1.0, rBreakEven + 0.15));
  }

  // Helper function to create a scenario
  const createScenario = (
    id: string,
    label: string,
    R: number
  ): Scenario => {
    // R = Reward:Risk multiple
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

  // Generate profit scenarios
  const profitScenarios: Scenario[] = profitRValues.map((R, index) =>
    createScenario(`P${index + 1}`, `Profit Scenario ${index + 1}`, R)
  );

  return {
    rBreakEven,
    costPerTrade,
    lossScenarios,
    profitScenarios,
  };
}
