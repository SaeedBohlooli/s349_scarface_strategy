import { useState, useMemo } from "react";
import {
  Box,
  Paper,
  Typography,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  Card,
  CardContent,
} from "@mui/material";
import { buildRiskRewardScenarios, type Scenario } from "./calc";

export default function RiskRewardCalculator() {
  const [capital, setCapital] = useState<string>("4000");
  const [winRatePct, setWinRatePct] = useState<string>("57.77");
  const [riskPerTrade, setRiskPerTrade] = useState<string>("400");
  const [slippagePct, setSlippagePct] = useState<string>("0.05");
  const [commissionPct, setCommissionPct] = useState<string>("5");
  const [numTrades, setNumTrades] = useState<string>("100");

  const result = useMemo(() => {
    const capitalNum = parseFloat(capital);
    const winRateNum = parseFloat(winRatePct);
    const riskPerTradeNum = parseFloat(riskPerTrade);
    const slippagePctNum = parseFloat(slippagePct) || 0;
    const commissionPctNum = parseFloat(commissionPct) || 0;
    const numTradesNum = parseFloat(numTrades) || 100;

    // Validation
    if (
      isNaN(capitalNum) ||
      capitalNum <= 0 ||
      isNaN(winRateNum) ||
      winRateNum <= 0 ||
      winRateNum >= 100 ||
      isNaN(riskPerTradeNum) ||
      riskPerTradeNum <= 0 ||
      isNaN(numTradesNum) ||
      numTradesNum <= 0 ||
      isNaN(slippagePctNum) ||
      slippagePctNum < 0 ||
      isNaN(commissionPctNum) ||
      commissionPctNum < 0
    ) {
      return null;
    }

    try {
      return buildRiskRewardScenarios({
        capital: capitalNum,
        winRatePct: winRateNum,
        riskPerTrade: riskPerTradeNum,
        slippagePct: slippagePctNum,
        commissionPct: commissionPctNum,
        numTrades: numTradesNum,
      });
    } catch {
      return null;
    }
  }, [
    capital,
    winRatePct,
    riskPerTrade,
    slippagePct,
    commissionPct,
    numTrades,
  ]);

  const formatRR = (rr: number): string => {
    // R:R means Risk:Reward, display as "1 : X.XX" (1 Risk : X.XX Reward)
    return `1 : ${rr.toFixed(2)}`;
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatPercent = (value: number): string => {
    const sign = value >= 0 ? "+" : "";
    return `${sign}${(value * 100).toFixed(1)}%`;
  };

  const renderScenarioTable = (
    scenarios: Scenario[],
    title: string,
    sectionType: "loss" | "breakeven" | "profit" = "loss"
  ) => {
    // Define colors for each section type with better visibility
    const sectionColors = {
      loss: {
        border: "error.main",
        bg: "rgba(211, 47, 47, 0.08)", // Light red background
        headerBg: "error.main",
        headerText: "#ffffff",
        accent: "error.main",
      },
      breakeven: {
        border: "warning.main",
        bg: "rgba(237, 108, 2, 0.08)", // Light orange background
        headerBg: "warning.main",
        headerText: "#000000",
        accent: "warning.main",
      },
      profit: {
        border: "success.main",
        bg: "rgba(46, 125, 50, 0.08)", // Light green background
        headerBg: "success.main",
        headerText: "#ffffff",
        accent: "success.main",
      },
    };

    const colors = sectionColors[sectionType];

    return (
      <Box sx={{ mb: 4 }}>
        <Box
          sx={{
            bgcolor: colors.headerBg,
            color: colors.headerText,
            p: 1.5,
            borderRadius: "4px 4px 0 0",
            mb: 0,
            boxShadow: 1,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {title}
          </Typography>
        </Box>
        <TableContainer
          component={Paper}
          variant="outlined"
          sx={{
            border: `2px solid`,
            borderColor: colors.border,
            borderTop: "none",
            borderRadius: "0 0 4px 4px",
            "& .MuiPaper-root": {
              bgcolor: colors.bg,
            },
            "& .MuiTableHead-root": {
              bgcolor: "rgba(0, 0, 0, 0.02)",
            },
            "& .MuiTableRow-root:hover": {
              bgcolor: "rgba(0, 0, 0, 0.04)",
            },
          }}
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>Scenario</TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  R:R (Risk:Reward)
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  Expectancy (R)
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  $ per trade
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  $ over {numTrades} trades
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  Updated Capital
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ fontWeight: 600, fontFamily: "monospace" }}
                >
                  % Change
                </TableCell>
                <TableCell align="center" sx={{ fontWeight: 600 }}>
                  Outcome
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {scenarios.map((scenario) => {
                const outcomeLabel =
                  scenario.outcome === "LOSING" && scenario.approxTradesToZero
                    ? `Losing (acct ~0 in ${scenario.approxTradesToZero} trades)`
                    : scenario.outcome === "PROFITABLE"
                    ? "Profitable"
                    : "Breakeven";

                return (
                  <TableRow key={scenario.id}>
                    <TableCell>{scenario.label}</TableCell>
                    <TableCell align="right" sx={{ fontFamily: "monospace" }}>
                      {formatRR(scenario.rewardMultiple)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "monospace",
                        color:
                          scenario.expectancyR > 0
                            ? "success.main"
                            : scenario.expectancyR < 0
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {scenario.expectancyR.toFixed(3)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "monospace",
                        color:
                          scenario.expectancyPerTrade > 0
                            ? "success.main"
                            : scenario.expectancyPerTrade < 0
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {formatCurrency(scenario.expectancyPerTrade)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "monospace",
                        color:
                          scenario.expectancyOverNTrades > 0
                            ? "success.main"
                            : scenario.expectancyOverNTrades < 0
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {formatCurrency(scenario.expectancyOverNTrades)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "monospace",
                        fontWeight: 600,
                        color:
                          scenario.updatedCapital > parseFloat(capital)
                            ? "success.main"
                            : scenario.updatedCapital < parseFloat(capital)
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {formatCurrency(scenario.updatedCapital)}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: "monospace",
                        color:
                          scenario.percentChange > 0
                            ? "success.main"
                            : scenario.percentChange < 0
                            ? "error.main"
                            : "text.secondary",
                      }}
                    >
                      {formatPercent(scenario.percentChange)}
                    </TableCell>
                    <TableCell align="center">
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          color:
                            scenario.outcome === "PROFITABLE"
                              ? "success.main"
                              : scenario.outcome === "LOSING"
                              ? "error.main"
                              : "warning.main",
                        }}
                      >
                        {outcomeLabel}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  const hasInvalidWinRate =
    winRatePct !== "" &&
    (parseFloat(winRatePct) <= 0 || parseFloat(winRatePct) >= 100);

  const riskPerTradeNum = parseFloat(riskPerTrade) || 0;
  const slippagePctNum = parseFloat(slippagePct) || 0;
  const commissionPctNum = parseFloat(commissionPct) || 0;
  const slippageDollar = (riskPerTradeNum * slippagePctNum) / 100;
  const commissionDollar = (riskPerTradeNum * commissionPctNum) / 100;

  return (
    <Box sx={{ mx: "auto", p: 3 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Risk & Reward Calculator
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        R:R = Risk:Reward ratio (Risk is always 1 unit)
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Capital"
              type="number"
              value={capital}
              onChange={(e) => setCapital(e.target.value)}
              inputProps={{ min: 0, step: 100 }}
            />
          </Box>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Win Rate (%)"
              type="number"
              value={winRatePct}
              onChange={(e) => setWinRatePct(e.target.value)}
              inputProps={{ min: 0, max: 100, step: 0.1 }}
              error={hasInvalidWinRate}
              helperText={
                hasInvalidWinRate ? "Win rate must be between 0 and 100" : ""
              }
            />
          </Box>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Risk per Trade ($)"
              type="number"
              value={riskPerTrade}
              onChange={(e) => setRiskPerTrade(e.target.value)}
              inputProps={{ min: 0, step: 1 }}
              error={
                riskPerTrade !== "" &&
                (parseFloat(riskPerTrade) <= 0 ||
                  (capital !== "" &&
                    parseFloat(riskPerTrade) > parseFloat(capital)))
              }
              helperText={
                riskPerTrade !== "" && parseFloat(riskPerTrade) <= 0
                  ? "Risk per trade must be greater than 0."
                  : riskPerTrade !== "" &&
                    capital !== "" &&
                    parseFloat(riskPerTrade) > parseFloat(capital)
                  ? "Warning: you are risking more than your total capital."
                  : ""
              }
            />
          </Box>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Slippage (%)"
              type="number"
              value={slippagePct}
              onChange={(e) => setSlippagePct(e.target.value)}
              inputProps={{ min: 0, step: 0.01 }}
              helperText="% of risk per trade"
            />
          </Box>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Commission (%)"
              type="number"
              value={commissionPct}
              onChange={(e) => setCommissionPct(e.target.value)}
              inputProps={{ min: 0, step: 0.01 }}
              helperText="% of risk per trade"
            />
          </Box>
          <Box sx={{ flex: "1 1 200px", minWidth: "200px" }}>
            <TextField
              fullWidth
              label="Number of Trades"
              type="number"
              value={numTrades}
              onChange={(e) => setNumTrades(e.target.value)}
              inputProps={{ min: 1, step: 1 }}
            />
          </Box>
        </Box>
      </Paper>

      {!result && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Please enter a valid capital and win rate (between 0 and 100).
        </Alert>
      )}

      {result && (
        <>
          {/* Summary Card */}
          <Card sx={{ mb: 4, bgcolor: "background.paper" }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Summary
              </Typography>
              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 3, mt: 2 }}>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Capital
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
                    {formatCurrency(parseFloat(capital))}
                  </Typography>
                </Box>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Win Rate
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
                    {parseFloat(winRatePct).toFixed(1)}%
                  </Typography>
                </Box>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Risk per Trade
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
                    {formatCurrency(parseFloat(riskPerTrade))}
                  </Typography>
                </Box>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Slippage
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
                    {slippagePctNum.toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatCurrency(slippageDollar)}
                  </Typography>
                </Box>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Commission
                  </Typography>
                  <Typography variant="h6" sx={{ fontFamily: "monospace" }}>
                    {commissionPctNum.toFixed(2)}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatCurrency(commissionDollar)}
                  </Typography>
                </Box>
                <Box sx={{ flex: "1 1 150px", minWidth: "150px" }}>
                  <Typography variant="body2" color="text.secondary">
                    Break-even R:R (Risk:Reward)
                  </Typography>
                  <Typography
                    variant="h6"
                    sx={{ fontFamily: "monospace", color: "warning.main" }}
                  >
                    {formatRR(result.rBreakEven)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    (net of slippage & commissions)
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* Loss Scenarios */}
          {result.lossScenarios.length > 0 &&
            renderScenarioTable(
              result.lossScenarios,
              "Loss Scenarios (R below break-even)",
              "loss"
            )}

          {/* Break-even Scenarios */}
          {result.breakEvenScenarios.length > 0 &&
            renderScenarioTable(
              result.breakEvenScenarios,
              "Break-even Scenarios",
              "breakeven"
            )}

          {/* Profit Scenarios (only positive) */}
          {result.profitScenarios.length > 0 &&
            renderScenarioTable(
              result.profitScenarios,
              "Profit Scenarios (R above break-even, positive expectancy only)",
              "profit"
            )}
        </>
      )}
    </Box>
  );
}
