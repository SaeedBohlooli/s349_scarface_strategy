"""
Intraday Level Detection and HTF Support/Resistance Module

This module implements a comprehensive system for detecting and scoring
trading levels from 1-minute OHLCV data, including:
- Daily anchors (PDH/PDL, PMH/PML)
- Intraday levels (5M/15M highs/lows, IB range)
- HTF swing levels (1H, 4H)
- Round number levels
- ATR-based projections

Author: Trading Strategy Development
Date: November 1, 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


@dataclass
class LevelCandidate:
    """Represents a potential support/resistance level with metadata"""
    level: float
    tags: List[str]
    score: float
    touches: int = 0
    distance: float = 0.0
    distance_atr: float = 0.0


class LevelsDetector:
    """
    Main class for detecting and scoring trading levels from OHLCV data
    """

    def __init__(self,
                 merge_bps: int = 8,
                 premarket_window: str = "04:00-09:29",
                 rth_window: str = "09:30-16:00",
                 htf_timeframes: List[str] = None,
                 swing_window: int = 5,
                 atr_period: int = 14):
        """
        Initialize the levels detector

        Args:
            merge_bps: Merge tolerance in basis points
            premarket_window: Premarket session window
            rth_window: Regular trading hours window
            htf_timeframes: Higher timeframe list for swing detection
            swing_window: Window for swing high/low detection
            atr_period: Period for ATR calculation
        """
        self.merge_bps = merge_bps
        self.premarket_window = premarket_window
        self.rth_window = rth_window
        self.htf_timeframes = htf_timeframes or ["1H", "4H"]
        self.swing_window = swing_window
        self.atr_period = atr_period

        # Parse session windows
        self._parse_session_windows()

        # Scoring weights
        self.weights = {
            'PDH_PDL': 3,
            'PMH_PML': 3,
            'IB': 2,
            'OR': 2,
            'swing_5m': 2,
            'swing_15m': 1,
            'HTF_swing': 2,
            'round_number': 1,
            'major_historical': 2,  # NEW: Major historical levels
            'weekly_level': 3,      # NEW: Weekly levels get high priority
            'touch_bonus': 0.5,
            'distance_penalty': -1
        }

    def _parse_session_windows(self):
        """Parse session window strings into time objects"""
        pm_start, pm_end = self.premarket_window.split('-')
        rth_start, rth_end = self.rth_window.split('-')

        self.pm_start = time(*map(int, pm_start.split(':')))
        self.pm_end = time(*map(int, pm_end.split(':')))
        self.rth_start = time(*map(int, rth_start.split(':')))
        self.rth_end = time(*map(int, rth_end.split(':')))

    def load_ohlcv_1m(self, path: Union[str, Path], tz: str = "America/New_York") -> pd.DataFrame:
        """
        Load 1-minute OHLCV data from CSV file

        Args:
            path: Path to CSV file
            tz: Timezone for data

        Returns:
            DataFrame with datetime index and OHLCV columns
        """
        df = pd.read_csv(path)

        # Ensure proper column names
        expected_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in expected_cols):
            raise ValueError(f"CSV must contain columns: {expected_cols}")

        # Convert to datetime and set timezone
        df['date'] = pd.to_datetime(df['date'])
        if df['date'].dt.tz is None:
            df['date'] = df['date'].dt.tz_localize(tz)
        else:
            df['date'] = df['date'].dt.tz_convert(tz)

        df.set_index('date', inplace=True)
        df.sort_index(inplace=True)

        return df

    def slice_to_asof(self, df: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
        """
        Slice dataframe to include only data up to the asof timestamp

        Args:
            df: Input dataframe with datetime index
            asof: Cut-off timestamp

        Returns:
            Sliced dataframe
        """
        if asof.tz is None:
            asof = asof.tz_localize(df.index.tz)
        elif asof.tz != df.index.tz:
            asof = asof.tz_convert(df.index.tz)

        return df[df.index <= asof]

    def compute_daily_anchors(self, df: pd.DataFrame, asof: pd.Timestamp) -> Dict[str, float]:
        """
        Compute daily anchor levels (PDH/PDL, PMH/PML)

        Args:
            df: OHLCV dataframe
            asof: Reference timestamp

        Returns:
            Dictionary with anchor levels
        """
        anchors = {}
        current_date = asof.date()
        previous_date = (asof - timedelta(days=1)).date()

        # Previous Day High/Low (RTH only)
        prev_day_data = df[df.index.date == previous_date]
        if not prev_day_data.empty:
            # Filter for RTH hours
            rth_data = self._filter_session(prev_day_data, 'rth')
            if not rth_data.empty:
                anchors['PDH'] = rth_data['high'].max()
                anchors['PDL'] = rth_data['low'].min()

        # Premarket High/Low (current day)
        current_day_data = df[df.index.date == current_date]
        if not current_day_data.empty:
            pm_data = self._filter_session(current_day_data, 'premarket')
            if not pm_data.empty:
                anchors['PMH'] = pm_data['high'].max()
                anchors['PML'] = pm_data['low'].min()

        return anchors

    def _filter_session(self, df: pd.DataFrame, session: str) -> pd.DataFrame:
        """Filter dataframe for specific session"""
        if session == 'premarket':
            return df[(df.index.time >= self.pm_start) & (df.index.time < self.pm_end)]
        elif session == 'rth':
            return df[(df.index.time >= self.rth_start) & (df.index.time < self.rth_end)]
        else:
            return df

    def resample_bars(self, df: pd.DataFrame, tf: str) -> pd.DataFrame:
        """
        Resample 1-minute bars to higher timeframe

        Args:
            df: Input 1-minute dataframe
            tf: Target timeframe (e.g., '5T', '15T', '1H', '4H')

        Returns:
            Resampled dataframe
        """
        # Map timeframe aliases
        tf_map = {
            '5M': '5T', '15M': '15T', '30M': '30T',
            '1H': '1H', '4H': '4H', '1D': '1D'
        }

        resample_tf = tf_map.get(tf, tf)

        resampled = df.resample(resample_tf).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        return resampled

    def intraday_levels(self, df: pd.DataFrame, asof: pd.Timestamp) -> Dict[str, float]:
        """
        Compute intraday levels (5M/15M highs/lows since RTH open)

        Args:
            df: 1-minute OHLCV data
            asof: Reference timestamp

        Returns:
            Dictionary with intraday levels
        """
        levels = {}
        current_date = asof.date()

        # Get current day RTH data
        current_day = df[df.index.date == current_date]
        rth_data = self._filter_session(current_day, 'rth')

        if rth_data.empty:
            return levels

        # Slice to asof
        rth_to_asof = self.slice_to_asof(rth_data, asof)

        if rth_to_asof.empty:
            return levels

        # 5-minute levels
        df_5m = self.resample_bars(rth_to_asof, '5M')
        if not df_5m.empty:
            levels['5MH'] = df_5m['high'].max()
            levels['5ML'] = df_5m['low'].min()

        # 15-minute levels
        df_15m = self.resample_bars(rth_to_asof, '15M')
        if not df_15m.empty:
            levels['15MH'] = df_15m['high'].max()
            levels['15ML'] = df_15m['low'].min()

        return levels

    def ib_range(self, df: pd.DataFrame, asof: pd.Timestamp) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute Initial Balance range (09:30-10:30)

        Args:
            df: 1-minute OHLCV data
            asof: Reference timestamp

        Returns:
            Tuple of (IB_High, IB_Low)
        """
        current_date = asof.date()
        current_day = df[df.index.date == current_date]

        # Define IB window (first hour of RTH)
        ib_start = datetime.combine(current_date, self.rth_start).replace(tzinfo=asof.tz)
        ib_end = ib_start + timedelta(hours=1)

        # Get IB data
        ib_data = current_day[(current_day.index >= ib_start) & (current_day.index < ib_end)]

        if ib_data.empty:
            return None, None

        # If asof is before IB end, slice accordingly
        if asof < ib_end:
            ib_data = self.slice_to_asof(ib_data, asof)

        if ib_data.empty:
            return None, None

        return ib_data['high'].max(), ib_data['low'].min()

    def find_swings(self, df: pd.DataFrame, window: int = None) -> Dict[str, List[float]]:
        """
        Find swing highs and lows using local extrema

        Args:
            df: OHLCV dataframe
            window: Window size for swing detection

        Returns:
            Dictionary with swing_highs and swing_lows lists
        """
        if window is None:
            window = self.swing_window

        if len(df) < window * 2 + 1:
            return {'swing_highs': [], 'swing_lows': []}

        highs = df['high'].values
        lows = df['low'].values

        swing_highs = []
        swing_lows = []

        # Find swing highs
        for i in range(window, len(highs) - window):
            if all(highs[i] >= highs[j] for j in range(i - window, i + window + 1) if j != i):
                if highs[i] == max(highs[i - window:i + window + 1]):
                    swing_highs.append(highs[i])

        # Find swing lows
        for i in range(window, len(lows) - window):
            if all(lows[i] <= lows[j] for j in range(i - window, i + window + 1) if j != i):
                if lows[i] == min(lows[i - window:i + window + 1]):
                    swing_lows.append(lows[i])

        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows
        }

    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> float:
        """
        Calculate Average True Range

        Args:
            df: OHLCV dataframe
            period: ATR period

        Returns:
            ATR value
        """
        if period is None:
            period = self.atr_period

        if len(df) < period:
            return df['high'].max() - df['low'].min()  # Fallback to range

        # Calculate True Range
        df = df.copy()
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        return df['tr'].tail(period).mean()

    def merge_levels(self, levels: List[float], tolerance_pct: float) -> List[float]:
        """
        Merge levels that are close together

        Args:
            levels: List of price levels
            tolerance_pct: Merge tolerance as percentage

        Returns:
            List of merged levels
        """
        if not levels:
            return []

        levels = sorted(levels)
        merged = [levels[0]]

        for level in levels[1:]:
            last_merged = merged[-1]
            if abs(level - last_merged) / last_merged <= tolerance_pct / 100:
                # Merge by taking average
                merged[-1] = (last_merged + level) / 2
            else:
                merged.append(level)

        return merged

    def get_round_numbers(self, price_range: Tuple[float, float], spacing: float = 1.0) -> List[float]:
        """
        Generate round number levels within price range

        Args:
            price_range: Tuple of (min_price, max_price)
            spacing: Spacing between round numbers

        Returns:
            List of round number levels
        """
        min_price, max_price = price_range

        # Determine appropriate spacing based on price level
        if max_price < 10:
            spacing = 0.25
        elif max_price < 50:
            spacing = 0.50
        elif max_price < 200:
            spacing = 1.0
        else:
            spacing = 5.0

        start = int(min_price / spacing) * spacing
        end = int(max_price / spacing + 1) * spacing

        rounds = []
        current = start
        while current <= end:
            if min_price <= current <= max_price:
                rounds.append(round(current, 2))
            current += spacing

        return rounds

    def get_major_historical_levels(self, df: pd.DataFrame, asof: pd.Timestamp,
                                   lookback_days: int = 10, min_significance_atr: float = 1.5) -> Dict[str, List[LevelCandidate]]:
        """
        Find major historical intraday levels from past trading days

        Args:
            df: OHLCV dataframe
            asof: Reference timestamp
            lookback_days: Number of trading days to look back
            min_significance_atr: Minimum ATR distance for level significance

        Returns:
            Dictionary with major historical resistance and support levels
        """
        df_to_asof = self.slice_to_asof(df, asof)
        current_price = df_to_asof['close'].iloc[-1]

        # Calculate 5M ATR for significance filtering
        df_5m = self.resample_bars(df_to_asof, '5M')
        atr_5m = self.calculate_atr(df_5m, self.atr_period)

        # Get unique trading dates, excluding current date
        current_date = asof.date()
        all_dates = sorted([d for d in df_to_asof.index.date if d < current_date], reverse=True)

        # Limit to lookback period
        target_dates = all_dates[:lookback_days] if len(all_dates) >= lookback_days else all_dates

        historical_candidates = []

        for i, trade_date in enumerate(target_dates):
            # Get data for this specific trading day
            day_data = df_to_asof[df_to_asof.index.date == trade_date]
            if day_data.empty:
                continue

            # Filter for RTH hours only for consistency
            rth_day_data = self._filter_session(day_data, 'rth')
            if rth_day_data.empty:
                continue

            # Calculate daily statistics
            day_high = rth_day_data['high'].max()
            day_low = rth_day_data['low'].min()
            day_volume = rth_day_data['volume'].sum()
            day_range = day_high - day_low

            # Calculate recency score (more recent = higher score)
            recency_score = max(0, 10 - i)  # 10 points for yesterday, 9 for day before, etc.

            # Volume significance (relative to average volume)
            avg_volume = df_to_asof['volume'].mean()
            volume_score = min(3, day_volume / avg_volume) if avg_volume > 0 else 1

            # Range significance
            range_score = min(3, day_range / atr_5m) if atr_5m > 0 else 1

            # Check for swing significance - did this day create major reversals?
            swing_score = 0
            if i > 0:  # Need previous day for comparison
                prev_date = target_dates[i-1] if i < len(target_dates) else None
                if prev_date:
                    prev_day_data = df_to_asof[df_to_asof.index.date == prev_date]
                    if not prev_day_data.empty:
                        prev_rth = self._filter_session(prev_day_data, 'rth')
                        if not prev_rth.empty:
                            prev_high = prev_rth['high'].max()
                            prev_low = prev_rth['low'].min()

                            # Check if this day made significant new highs/lows
                            if day_high > prev_high + atr_5m * min_significance_atr:
                                swing_score += 2  # Significant breakout high
                            if day_low < prev_low - atr_5m * min_significance_atr:
                                swing_score += 2  # Significant breakdown low

            # Create level candidates for this day's high and low
            base_score = recency_score + volume_score + range_score + swing_score

            # High level candidate
            high_distance = abs(day_high - current_price)
            high_distance_atr = high_distance / atr_5m if atr_5m > 0 else 0

            high_candidate = LevelCandidate(
                level=day_high,
                tags=[f'historical_day_{i+1}_high', f'date_{trade_date}', 'major_historical'],
                score=base_score,
                distance=high_distance,
                distance_atr=high_distance_atr
            )

            # Low level candidate
            low_distance = abs(day_low - current_price)
            low_distance_atr = low_distance / atr_5m if atr_5m > 0 else 0

            low_candidate = LevelCandidate(
                level=day_low,
                tags=[f'historical_day_{i+1}_low', f'date_{trade_date}', 'major_historical'],
                score=base_score,
                distance=low_distance,
                distance_atr=low_distance_atr
            )

            historical_candidates.extend([high_candidate, low_candidate])

        # Add weekly levels (if we have enough data)
        if len(target_dates) >= 5:  # At least a week of data
            weekly_candidates = self._get_weekly_levels(df_to_asof, asof, current_price, atr_5m)
            historical_candidates.extend(weekly_candidates)

        # Filter out levels too close to current price (less than 0.5 ATR)
        min_distance_atr = 0.5
        significant_candidates = [
            c for c in historical_candidates
            if c.distance_atr >= min_distance_atr
        ]

        # Separate resistance and support
        resistance_candidates = [c for c in significant_candidates if c.level > current_price]
        support_candidates = [c for c in significant_candidates if c.level < current_price]

        # Sort by score and distance
        resistance_candidates.sort(key=lambda x: (-x.score, x.distance))
        support_candidates.sort(key=lambda x: (-x.score, x.distance))

        return {
            'resistance': resistance_candidates[:6],  # Top 6 historical resistance levels
            'support': support_candidates[:6]        # Top 6 historical support levels
        }

    def _get_weekly_levels(self, df: pd.DataFrame, asof: pd.Timestamp,
                          current_price: float, atr_5m: float) -> List[LevelCandidate]:
        """
        Get weekly high/low levels from past weeks

        Args:
            df: OHLCV dataframe
            asof: Reference timestamp
            current_price: Current market price
            atr_5m: 5-minute ATR for distance calculation

        Returns:
            List of weekly level candidates
        """
        weekly_candidates = []

        # Resample to weekly bars (Monday-Friday)
        try:
            # Filter to RTH only first
            rth_data = df[(df.index.time >= self.rth_start) & (df.index.time < self.rth_end)]

            # Resample to weekly (W-FRI = week ending Friday)
            weekly_df = rth_data.resample('W-FRI').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

            # Get last 4 weeks (excluding current incomplete week)
            current_week = asof.isocalendar().week
            completed_weeks = weekly_df[weekly_df.index < asof - timedelta(days=asof.weekday())]
            recent_weeks = completed_weeks.tail(4)

            for i, (week_end, week_data) in enumerate(recent_weeks.iterrows()):
                week_high = week_data['high']
                week_low = week_data['low']
                week_volume = week_data['volume']

                # Recency score (more recent weeks get higher scores)
                recency_score = max(0, 8 - i * 2)  # 8, 6, 4, 2 for last 4 weeks

                # Volume score
                avg_weekly_volume = recent_weeks['volume'].mean()
                volume_score = min(2, week_volume / avg_weekly_volume) if avg_weekly_volume > 0 else 1

                base_score = recency_score + volume_score + 2  # +2 for being weekly level

                # Weekly high candidate
                high_distance = abs(week_high - current_price)
                high_distance_atr = high_distance / atr_5m if atr_5m > 0 else 0

                high_candidate = LevelCandidate(
                    level=week_high,
                    tags=[f'weekly_high_w{i+1}', f'week_end_{week_end.date()}', 'major_historical'],
                    score=base_score,
                    distance=high_distance,
                    distance_atr=high_distance_atr
                )

                # Weekly low candidate
                low_distance = abs(week_low - current_price)
                low_distance_atr = low_distance / atr_5m if atr_5m > 0 else 0

                low_candidate = LevelCandidate(
                    level=week_low,
                    tags=[f'weekly_low_w{i+1}', f'week_end_{week_end.date()}', 'major_historical'],
                    score=base_score,
                    distance=low_distance,
                    distance_atr=low_distance_atr
                )

                weekly_candidates.extend([high_candidate, low_candidate])

        except Exception as e:
            # If weekly resampling fails, continue without weekly levels
            pass

        return weekly_candidates

    def build_candidates(self, df: pd.DataFrame, asof: pd.Timestamp,
                        current_price: float) -> List[LevelCandidate]:
        """
        Build list of all level candidates with tags

        Args:
            df: OHLCV dataframe
            asof: Reference timestamp
            current_price: Current market price

        Returns:
            List of LevelCandidate objects
        """
        candidates = []

        # Daily anchors
        anchors = self.compute_daily_anchors(df, asof)
        for tag, level in anchors.items():
            candidates.append(LevelCandidate(level=level, tags=[tag], score=0))

        # Intraday levels
        intraday = self.intraday_levels(df, asof)
        for tag, level in intraday.items():
            candidates.append(LevelCandidate(level=level, tags=[tag], score=0))

        # IB Range
        ib_high, ib_low = self.ib_range(df, asof)
        if ib_high is not None:
            candidates.append(LevelCandidate(level=ib_high, tags=['IB_High'], score=0))
        if ib_low is not None:
            candidates.append(LevelCandidate(level=ib_low, tags=['IB_Low'], score=0))

        # HTF Swings
        for tf in self.htf_timeframes:
            htf_df = self.resample_bars(df, tf)
            htf_to_asof = self.slice_to_asof(htf_df, asof)

            if not htf_to_asof.empty:
                swings = self.find_swings(htf_to_asof)

                for high in swings['swing_highs']:
                    candidates.append(LevelCandidate(
                        level=high,
                        tags=[f'HTF_{tf}_swing_high'],
                        score=0
                    ))

                for low in swings['swing_lows']:
                    candidates.append(LevelCandidate(
                        level=low,
                        tags=[f'HTF_{tf}_swing_low'],
                        score=0
                    ))

        # 5M and 15M swings
        for tf_min in [5, 15]:
            tf_data = self.resample_bars(df, f'{tf_min}M')
            tf_to_asof = self.slice_to_asof(tf_data, asof)

            if not tf_to_asof.empty:
                swings = self.find_swings(tf_to_asof)

                for high in swings['swing_highs']:
                    candidates.append(LevelCandidate(
                        level=high,
                        tags=[f'swing_{tf_min}m_high'],
                        score=0
                    ))

                for low in swings['swing_lows']:
                    candidates.append(LevelCandidate(
                        level=low,
                        tags=[f'swing_{tf_min}m_low'],
                        score=0
                    ))

        # Major Historical Levels (NEW!)
        try:
            historical_levels = self.get_major_historical_levels(df, asof, lookback_days=10)

            # Add historical resistance levels
            for hist_candidate in historical_levels['resistance'][:3]:  # Top 3 historical resistance
                candidates.append(hist_candidate)

            # Add historical support levels
            for hist_candidate in historical_levels['support'][:3]:   # Top 3 historical support
                candidates.append(hist_candidate)

        except Exception as e:
            # If historical level detection fails, continue without them
            pass

        # Round numbers
        price_range = (current_price * 0.95, current_price * 1.05)
        round_levels = self.get_round_numbers(price_range)
        for level in round_levels:
            candidates.append(LevelCandidate(level=level, tags=['round'], score=0))

        return candidates

    def score_candidates(self, candidates: List[LevelCandidate],
                        atr_5m: float, current_price: float) -> List[LevelCandidate]:
        """
        Score all level candidates

        Args:
            candidates: List of level candidates
            atr_5m: 5-minute ATR value
            current_price: Current market price

        Returns:
            List of scored candidates
        """
        tolerance_frac = self.merge_bps / 10000  # Convert bps to fraction

        # Merge similar levels first
        level_groups = {}
        for candidate in candidates:
            merged = False
            for base_level in level_groups:
                if abs(candidate.level - base_level) / base_level <= tolerance_frac:
                    level_groups[base_level].append(candidate)
                    merged = True
                    break

            if not merged:
                level_groups[candidate.level] = [candidate]

        # Score merged candidates
        scored_candidates = []

        for base_level, group in level_groups.items():
            # Merge level (average)
            merged_level = sum(c.level for c in group) / len(group)

            # Union all tags
            all_tags = []
            for candidate in group:
                all_tags.extend(candidate.tags)
            unique_tags = list(set(all_tags))

            # Calculate score
            score = 0

            # Base scores by tag type
            for tag in unique_tags:
                if tag in ['PDH', 'PDL']:
                    score += self.weights['PDH_PDL']
                elif tag in ['PMH', 'PML']:
                    score += self.weights['PMH_PML']
                elif 'IB' in tag:
                    score += self.weights['IB']
                elif 'swing_5m' in tag:
                    score += self.weights['swing_5m']
                elif 'swing_15m' in tag:
                    score += self.weights['swing_15m']
                elif 'HTF' in tag:
                    score += self.weights['HTF_swing']
                elif tag == 'round':
                    score += self.weights['round_number']
                elif 'major_historical' in tag:
                    score += self.weights['major_historical']
                elif 'weekly_' in tag:
                    score += self.weights['weekly_level']
                elif 'historical_day_' in tag:
                    # Extract day number and apply decreasing score
                    try:
                        day_num = int(tag.split('_')[2])
                        day_score = max(1, 4 - (day_num - 1) * 0.5)  # 4, 3.5, 3, 2.5, etc.
                        score += day_score
                    except:
                        score += self.weights['major_historical']

            # Distance penalty
            distance = abs(merged_level - current_price)
            distance_atr = distance / atr_5m if atr_5m > 0 else 0

            if distance_atr > 1.5:
                score += self.weights['distance_penalty']

            # Create merged candidate
            merged_candidate = LevelCandidate(
                level=merged_level,
                tags=unique_tags,
                score=score,
                distance=distance,
                distance_atr=distance_atr
            )

            scored_candidates.append(merged_candidate)

        return scored_candidates

    def next_levels(self, candidates: List[LevelCandidate],
                   current_price: float, topk: int = 3) -> Dict[str, List[Dict]]:
        """
        Select next resistance and support levels

        Args:
            candidates: Scored level candidates
            current_price: Current market price
            topk: Number of levels to return for each side

        Returns:
            Dictionary with resistance and support level lists
        """
        # Separate resistance (above) and support (below)
        resistance = [c for c in candidates if c.level > current_price]
        support = [c for c in candidates if c.level < current_price]

        # Sort resistance by score (desc) then distance (asc)
        resistance.sort(key=lambda x: (-x.score, x.distance))

        # Sort support by score (desc) then distance (asc)
        support.sort(key=lambda x: (-x.score, x.distance))

        # Format output
        def format_level(candidate: LevelCandidate) -> Dict:
            return {
                'level': round(candidate.level, 2),
                'tags': candidate.tags,
                'score': candidate.score,
                'distance': round(candidate.level - current_price, 2),
                'distance_atr': round(candidate.distance_atr, 2)
            }

        return {
            'resistance': [format_level(c) for c in resistance[:topk]],
            'support': [format_level(c) for c in support[:topk]]
        }

    def _build_levels_by_price(self, levels_dict: Dict[str, float], current_price: float,
                              atr_5m: float, next_levels: Dict, major_historical: Dict) -> Dict:
        """
        Build levelsByPrice structure organizing intraday levels by price value

        Args:
            levels_dict: Dictionary of level names to prices
            current_price: Current market price
            atr_5m: 5-minute ATR value
            next_levels: Next levels structure from main analysis
            major_historical: Major historical levels

        Returns:
            Dictionary organized by price levels
        """
        levels_by_price = {}

        # Get all intraday levels with their prices
        intraday_levels = {}
        for name, price in levels_dict.items():
            if name in ['PDH', 'PDL', 'PMH', 'PML', '5MH', '5ML', 'IB_High', 'IB_Low']:
                intraday_levels[name] = price

        # Find min and max of intraday levels
        if not intraday_levels:
            return levels_by_price

        min_intraday = min(intraday_levels.values())
        max_intraday = max(intraday_levels.values())

        # Get historical levels above max and below min intraday levels
        historical_resistance = []
        historical_support = []

        # From next_levels - only levels outside intraday range
        for level_info in next_levels.get('resistance', []):
            if level_info['level'] > max_intraday + 1.0:  # At least 1 point above max intraday
                historical_resistance.append({
                    'level': level_info['level'],
                    'name': f"hist_{level_info['level']:.2f}",
                    'distance': level_info['distance'],
                    'distance_atr': level_info['distance_atr']
                })

        for level_info in next_levels.get('support', []):
            if level_info['level'] < min_intraday - 1.0:  # At least 1 point below min intraday
                historical_support.append({
                    'level': level_info['level'],
                    'name': f"hist_{level_info['level']:.2f}",
                    'distance': level_info['distance'],
                    'distance_atr': level_info['distance_atr']
                })

        # From major_historical_levels - only levels outside intraday range
        for level_info in major_historical.get('resistance', []):
            if level_info['level'] > max_intraday + 1.0:
                historical_resistance.append({
                    'level': level_info['level'],
                    'name': f"hist_{level_info['level']:.2f}",
                    'distance': level_info['distance'],
                    'distance_atr': level_info['distance_atr']
                })

        for level_info in major_historical.get('support', []):
            if level_info['level'] < min_intraday - 1.0:
                historical_support.append({
                    'level': level_info['level'],
                    'name': f"hist_{level_info['level']:.2f}",
                    'distance': level_info['distance'],
                    'distance_atr': level_info['distance_atr']
                })

        # Remove duplicates and sort
        historical_resistance = sorted(
            {h['level']: h for h in historical_resistance}.values(),
            key=lambda x: x['level']
        )
        historical_support = sorted(
            {h['level']: h for h in historical_support}.values(),
            key=lambda x: -x['level']  # Sort descending for support
        )

        # Build levelsByPrice for each intraday level
        processed_prices = set()

        for level_name, level_price in intraday_levels.items():
            # Skip if we already processed a very similar price
            price_key = str(round(level_price, 2))
            if any(abs(level_price - float(p)) < 0.25 for p in processed_prices):
                continue

            # Find levels within 0.25 points to group together
            grouped_levels = []
            for other_name, other_price in intraday_levels.items():
                if abs(other_price - level_price) <= 0.25:
                    grouped_levels.append((other_name, other_price))

            # Sort by price and create name
            grouped_levels.sort(key=lambda x: x[1])
            if len(grouped_levels) == 1:
                grouped_name = grouped_levels[0][0]
                final_price = grouped_levels[0][1]
            else:
                grouped_name = "/".join([g[0] for g in grouped_levels])
                final_price = sum(g[1] for g in grouped_levels) / len(grouped_levels)

            processed_prices.add(str(round(final_price, 2)))

            # Determine if this level is currently acting as support or resistance
            side = "resistance" if final_price > current_price else "support"

            # Find nearest resistance levels above this level
            resistance_levels = {}

            # Add intraday resistance levels
            for other_name, other_price in intraday_levels.items():
                if other_price > final_price + 0.25:  # Must be meaningfully above
                    distance = other_price - final_price
                    distance_atr = distance / atr_5m if atr_5m > 0 else 0
                    resistance_levels[other_name] = {
                        "distance": round(distance, 2),
                        "distance_atr": round(distance_atr, 4),
                        "price": round(other_price, 2)
                    }

            # Add historical resistance levels (limit to 2)
            for hist_level in historical_resistance[:2]:
                if hist_level['level'] > final_price:
                    resistance_levels[hist_level['name']] = {
                        "distance": round(hist_level['level'] - final_price, 2),
                        "distance_atr": round((hist_level['level'] - final_price) / atr_5m, 4) if atr_5m > 0 else 0,
                        "price": round(hist_level['level'], 2)
                    }

            # Find nearest support levels below this level
            support_levels = {}

            # Add intraday support levels
            for other_name, other_price in intraday_levels.items():
                if other_price < final_price - 0.25:  # Must be meaningfully below
                    distance = other_price - final_price  # Negative for support
                    distance_atr = distance / atr_5m if atr_5m > 0 else 0
                    support_levels[other_name] = {
                        "distance": round(distance, 2),
                        "distance_atr": round(distance_atr, 4),
                        "price": round(other_price, 2)
                    }

            # Add historical support levels (limit to 2)
            for hist_level in historical_support[:2]:
                if hist_level['level'] < final_price:
                    support_levels[hist_level['name']] = {
                        "distance": round(hist_level['level'] - final_price, 2),
                        "distance_atr": round((hist_level['level'] - final_price) / atr_5m, 4) if atr_5m > 0 else 0,
                        "price": round(hist_level['level'], 2)
                    }

            # Sort and take closest levels
            closest_resistance = dict(sorted(resistance_levels.items(),
                                           key=lambda x: x[1]['distance'])[:3])
            closest_support = dict(sorted(support_levels.items(),
                                        key=lambda x: -x[1]['distance'])[:3])  # Closest to zero (least negative)

            levels_by_price[price_key] = {
                "level": grouped_name,
                "distance": round(final_price - current_price, 2),
                "distance_atr": round((final_price - current_price) / atr_5m, 4) if atr_5m > 0 else 0,
                "side": side,
                "resistanceLevels": closest_resistance,
                "supportLevels": closest_support
            }

        return levels_by_price

    def detect_levels(self, df: pd.DataFrame, asof: pd.Timestamp,
                     symbol: str = "UNKNOWN") -> Dict:
        """
        Main method to detect and score all levels

        Args:
            df: OHLCV dataframe
            asof: Reference timestamp
            symbol: Trading symbol

        Returns:
            Complete levels analysis as dictionary
        """
        # Slice data to asof
        df_to_asof = self.slice_to_asof(df, asof)

        if df_to_asof.empty:
            raise ValueError("No data available up to asof timestamp")

        # Get current price
        current_price = df_to_asof['close'].iloc[-1]

        # Calculate 5M ATR
        df_5m = self.resample_bars(df_to_asof, '5M')
        atr_5m = self.calculate_atr(df_5m, self.atr_period)

        # Get all basic levels
        anchors = self.compute_daily_anchors(df, asof)
        intraday = self.intraday_levels(df, asof)
        ib_high, ib_low = self.ib_range(df, asof)

        # Get major historical levels separately for detailed output
        try:
            major_historical = self.get_major_historical_levels(df, asof, lookback_days=10)
        except Exception as e:
            major_historical = {'resistance': [], 'support': []}

        # Build and score candidates
        candidates = self.build_candidates(df, asof, current_price)
        scored_candidates = self.score_candidates(candidates, atr_5m, current_price)

        # Get next levels
        next_lvls = self.next_levels(scored_candidates, current_price, topk=3)

        # Build response
        levels_dict = {**anchors, **intraday}
        if ib_high is not None:
            levels_dict['IB_High'] = ib_high
        if ib_low is not None:
            levels_dict['IB_Low'] = ib_low

        # Format major historical levels for output
        def format_historical_level(candidate: LevelCandidate) -> Dict:
            return {
                'level': round(candidate.level, 2),
                'tags': candidate.tags,
                'score': candidate.score,
                'distance': round(candidate.level - current_price, 2),
                'distance_atr': round(candidate.distance_atr, 2)
            }

        major_historical_formatted = {
            'resistance': [format_historical_level(c) for c in major_historical['resistance'][:3]],
            'support': [format_historical_level(c) for c in major_historical['support'][:3]]
        }

        # Generate levelsByPrice structure
        levels_by_price = self._build_levels_by_price(levels_dict, current_price, atr_5m,
                                                     next_lvls, major_historical_formatted)

        result = {
            'asof': asof.isoformat(),
            'symbol': symbol,
            'last_price': round(current_price, 2),
            'levels': {k: round(v, 2) for k, v in levels_dict.items()},
            'levelsByPrice': levels_by_price,  # NEW: Levels organized by price
            'next_levels': next_lvls,
            'major_historical_levels': major_historical_formatted,  # NEW: Separate section for major historical levels
            'meta': {
                'atr_5m': round(atr_5m, 2),
                'ib_high': round(ib_high, 2) if ib_high else None,
                'ib_low': round(ib_low, 2) if ib_low else None,
                'historical_lookback_days': 10,  # NEW: Document lookback period
                'total_candidates': len(candidates),  # NEW: Debug info
                'params': {
                    'merge_bps': self.merge_bps,
                    'premarket': self.premarket_window,
                    'rth': self.rth_window,
                    'htf_timeframes': self.htf_timeframes
                }
            }
        }

        return result


def detect_levels_from_file(file_path: str, asof_str: str,
                           symbol: str = "UNKNOWN", output_file: str = None, **kwargs) -> Dict:
    """
    Convenience function to detect levels from file

    Args:
        file_path: Path to OHLCV CSV file
        asof_str: As-of timestamp string
        symbol: Trading symbol
        output_file: Optional path to save JSON output file
        **kwargs: Additional parameters for LevelsDetector

    Returns:
        Levels analysis dictionary
    """
    import json
    import os

    detector = LevelsDetector(**kwargs)

    # Load data
    df = detector.load_ohlcv_1m(file_path)

    # Parse asof timestamp
    asof = pd.to_datetime(asof_str)
    if asof.tz is None:
        asof = asof.tz_localize(df.index.tz)

    result = detector.detect_levels(df, asof, symbol)

    # Save to output file if specified
    if output_file:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Write JSON file
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✅ Levels analysis saved to: {output_file}")

    return result
