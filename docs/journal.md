# 📊 BNR Trade Dataset Schema

This document defines the CSV structure for the **Break-and-Retest (BNR)** trading dataset.  
It is used for collecting structured data for backtesting, analytics, and machine learning feature engineering.

---

## 🧩 1. Core Trade Information

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **Symbol** | string | Stock ticker (e.g., TSLA, AMD, NVDA). | Identifies instrument for cross-symbol comparison and sector analysis. |
| **Date** | date | Trading date (YYYY-MM-DD). | Enables day-level grouping and backtesting. |
| **Side** | enum(`CALL`, `PUT`) | Directional bias of trade. | Determines if signal aligned with QQQ trend. |
| **EntryTime** | time | HH:MM timestamp of entry. | Analyzes time-of-day edge (e.g., pre-10AM traps). |
| **ExitTime** | time | HH:MM timestamp of exit. | Used for hold-time metrics and session analysis. |
| **PNL** | int / float | Profit or loss (1/-1 or % return). | Evaluates win rate and expectancy. |
| **QQQ_Context** | enum(`PDH`, `PDL`, `Range`) | Whether QQQ was above PDH, below PDL, or range-bound at entry. | Measures trade success relative to market bias. |

---

## 🧱 2. Break Candle Features

These describe the first candle that **breaks a key level** (e.g., PDH/PDL/5MH/5ML).

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **Break_Open, Break_High, Break_Low, Break_Close** | float | OHLC data of break candle. | Captures structural strength of breakout. |
| **Break_ATR** | float | ATR(14) value at break. | Measures volatility context — large ATR = explosive breakout. |
| **Break_Volume** | float | Raw volume. | Indicates participation strength. |
| **Break_VolumeRatio** | float | Volume / AvgVolume(20). | High ratio confirms genuine breakout. |
| **Break_RS** | float | Relative Strength vs QQQ. | Quantifies stock’s performance vs index at breakout. |
| **Break_RS_Delta** | float | RS change from previous candle. | Detects RS acceleration or slowdown. |
| **Break_RS_RoC** | float | Rate of change of RS. | Early momentum indicator before visible price follow-through. |
| **Break_RS_Rel** | float | RS ratio (>1 strong, <1 weak). | Compares relative intensity of move. |
| **Break_RSI** | float | RSI value at break candle. | Momentum confirmation / overextension filter. |
| **Break_RSI_Div** | bool | RSI divergence flag. | Identifies potential fake breaks. |
| **Break_BodyPct** | float | \|close-open\| ÷ ATR. | Measures strength of candle body relative to volatility. |
| **Break_BodyDir** | enum(`UP`,`DOWN`) | Direction of breakout candle. | Useful for validating breakout alignment with trade side. |

---

## 🔁 3. Retest Candle Features

These describe the candle that **retests** the breakout level within the next few bars.

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **Retest_Open, Retest_High, Retest_Low, Retest_Close** | float | OHLC data of retest candle. | Confirms price reaction and absorption strength. |
| **Retest_ATR** | float | ATR(14) at retest. | Tests if volatility compresses — ideal for tight entry. |
| **Retest_Volume** | float | Volume on retest candle. | Lower volume = healthy retest, high = rejection risk. |
| **Retest_VolumeRatio** | float | Volume / AvgVolume(20). | Validates quality of pullback. |
| **Retest_RS, Retest_RS_Delta, Retest_RS_RoC, Retest_RS_Rel** | float | RS metrics during retest. | Shows whether stock retains or loses strength vs QQQ. |
| **Retest_RSI, Retest_RSI_Div** | float / bool | RSI indicators at retest. | Filters early reversals or hidden divergence setups. |
| **Retest_BodyPct, Retest_BodyDir** | float / enum | Candle body properties. | Characterizes reaction structure. |
| **Retest_TouchDistance** | float | Distance from breakout level (pts or ATR). | Defines tolerance for clean vs failed retests. |
| **Retest_TimeGap** | int | Minutes between break and retest. | Helps detect fast vs delayed retests. |

---

## 🎯 4. Entry Candle Features

These describe the candle where the **entry trigger fires**.

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **Entry_Open, Entry_High, Entry_Low, Entry_Close** | float | OHLC data of entry candle. | Baseline for calculating risk/reward metrics. |
| **Entry_ATR** | float | ATR(14) at entry. | Confirms volatility state at execution. |
| **Entry_Volume, Entry_VolumeRatio** | float | Volume metrics at entry. | Higher confirms commitment. |
| **Entry_RS, Entry_RS_Delta, Entry_RS_RoC, Entry_RS_Rel** | float | RS metrics at entry. | Ensures trade direction aligns with RS momentum. |
| **Entry_RSI, Entry_RSI_Div** | float / bool | RSI at entry. | Confirms if signal aligns with internal momentum. |
| **Entry_BodyPct, Entry_BodyDir** | float / enum | Candle structure at trigger. | Helps identify impulsive entries. |
| **Entry_TriggerType** | enum(`touch-high`,`close-above`,`limit-fill`) | Defines entry rule type. | Evaluates which trigger yields higher win rate. |

---

## 🧠 5. QQQ Context Snapshot

QQQ metrics captured at the **entry candle** time.

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **QQQ_ATR** | float | ATR(14) of QQQ. | Determines market volatility environment. |
| **QQQ_Volume, QQQ_VolumeRatio** | float | QQQ volume metrics. | Shows index participation strength. |
| **QQQ_RS** | float | RS of QQQ vs itself (baseline). | For normalization if computing RS deltas. |
| **QQQ_RSI** | float | RSI of QQQ. | Indicates overbought/oversold state. |
| **QQQ_Direction** | enum(`UP`,`DOWN`,`RANGE`) | Market direction at entry. | Crucial for trend alignment filtering. |
| **QQQ_PositionFromPDH, QQQ_PositionFromPDL** | float | Price distance from PDH/PDL in points or %. | Measures how extended QQQ is beyond prior levels. |

---

## 🧮 6. Derived & Meta Features

| Column | Type | Description | Why It’s Useful |
|---------|------|--------------|-----------------|
| **BreakToRetest_ATR_Change** | float | `Retest_ATR - Break_ATR`. | Detects volatility compression before entry. |
| **BreakToRetest_RS_Change** | float | `Retest_RS - Break_RS`. | Quantifies RS recovery or weakness. |
| **BreakToEntry_VolumeRatio_Change** | float | `Entry_VolumeRatio - Break_VolumeRatio`. | Highlights exhaustion or momentum continuation. |
| **Setup_QualityScore** | int (0–10) | Manually or programmatically assigned setup score. | Enables supervised learning or backtest labeling. |
| **Comment** | string | Analyst remarks. | For manual insights or anomaly tagging. |

---

## 🧾 7. Notes for Developers

- **Granularity:** Each row = one *trade setup* (not one candle).  
- **Timeframe:** Prefer 1-minute resolution for accuracy.  
- **Level Reference:** Break/Retest should reference whichever structural level (PDH, PDL, 5MH, etc.) triggered the setup.  
- **Data Sync:** Ensure timestamps between stock and QQQ data are aligned (NY timezone).  
- **Normalization:** For modeling, normalize RS, ATR, and VolumeRatio per symbol.  

---

## ✅ Example CSV Rows (Simplified)

Below are sample rows showing how full **Break–Retest–Entry** records might look in your dataset.  
These examples illustrate how OHLC, RS, ATR, and QQQ context fields align across each phase of a setup, and how different outcomes (win/loss) appear in the data.

---

### 🧾 Simplified View (Aggregated Table)

| Symbol | Date | Side | EntryTime | ExitTime | PNL | QQQ_Context | Break_ATR | Retest_ATR | Entry_ATR | Break_RS | Retest_RS | Entry_RS | Break_VolumeRatio | Retest_VolumeRatio | Entry_VolumeRatio | Break_RSI | Entry_RSI | RS_Rel | Entry_TriggerType | Setup_QualityScore | Comment |
|:-------|:------|:-----|:-----------|:----------|:-----|:--------------|:-----------|:------------|:-----------|:-----------|:-----------|:-----------|:------------------|:------------------|:-----------------|:-----------|:-----------|:--------|:------------------|:-------------------|:----------|
| **TSLA** | 2025-11-07 | PUT | 09:45 | 10:15 | -1 | PDL | 1.50 | 1.20 | 1.10 | -0.012 | -0.015 | -0.014 | 1.80 | 0.90 | 1.00 | 48 | 46 | 0.95 | touch-high | 5 | Failed retest — strong RS divergence before entry |
| **AMD** | 2025-11-06 | CALL | 10:12 | 10:45 | +1 | PDH | 1.20 | 0.95 | 1.05 | 0.008 | 0.012 | 0.015 | 1.10 | 0.85 | 1.30 | 54 | 61 | 1.25 | close-above | 8 | Clean break and steady RS increase across phases |
| **NVDA** | 2025-11-07 | PUT | 09:52 | 10:20 | 0 | PDL | 1.40 | 1.10 | 1.25 | -0.006 | -0.008 | -0.009 | 1.50 | 1.00 | 1.20 | 50 | 49 | 0.98 | touch-high | 6 | Extended move, partial retrace before flattening |

---

### 🧩 Full CSV Format for Developers

For developers logging or parsing trades, each row in the CSV should include **all columns** as defined in the schema:

```csv
Symbol,Date,Side,EntryTime,ExitTime,PNL,QQQ_Context,
Break_Open,Break_High,Break_Low,Break_Close,Break_ATR,Break_Volume,Break_VolumeRatio,Break_RS,Break_RS_Delta,Break_RS_RoC,Break_RS_Rel,Break_RSI,Break_RSI_Div,Break_BodyPct,Break_BodyDir,
Retest_Open,Retest_High,Retest_Low,Retest_Close,Retest_ATR,Retest_Volume,Retest_VolumeRatio,Retest_RS,Retest_RS_Delta,Retest_RS_RoC,Retest_RS_Rel,Retest_RSI,Retest_RSI_Div,Retest_BodyPct,Retest_BodyDir,Retest_TouchDistance,Retest_TimeGap,
Entry_Open,Entry_High,Entry_Low,Entry_Close,Entry_ATR,Entry_Volume,Entry_VolumeRatio,Entry_RS,Entry_RS_Delta,Entry_RS_RoC,Entry_RS_Rel,Entry_RSI,Entry_RSI_Div,Entry_BodyPct,Entry_BodyDir,Entry_TriggerType,
QQQ_ATR,QQQ_Volume,QQQ_VolumeRatio,QQQ_RS,QQQ_RSI,QQQ_Direction,QQQ_PositionFromPDH,QQQ_PositionFromPDL,
BreakToRetest_ATR_Change,BreakToRetest_RS_Change,BreakToEntry_VolumeRatio_Change,Setup_QualityScore,Comment


---

**Author:** Zynfosoft Quant Research  
**Version:** 1.0 (Nov 2025)  
**Purpose:** Unified schema for algorithmic BNR system data collection and analytics.
