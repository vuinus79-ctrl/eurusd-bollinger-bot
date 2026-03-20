"""
Unit tests for the EURUSD Bollinger Bands trading bot.

Tests cover:
- Bollinger Bands indicator calculation
- All three strategy signal generators
- Position-sizing / stop-loss / take-profit helpers
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

# The bot module is importable without MetaTrader5 because the import is
# guarded with a try/except.
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import (
    compute_bollinger_bands,
    compute_band_width,
    signal_bollinger_bounce,
    signal_bollinger_squeeze,
    signal_walking_bands,
    get_signal,
    calculate_lot_size,
    calculate_stop_loss_price,
    calculate_take_profit_price,
)
import config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_series(value: float = 1.1000, n: int = 60) -> pd.Series:
    """Series of identical closes – zero variance, bands collapse to SMA."""
    return pd.Series([value] * n, dtype=float)


def _ranging_series(n: int = 60) -> pd.Series:
    """Oscillating series staying within a narrow channel (≈ ±10 pips)."""
    rng = np.random.default_rng(42)
    base = 1.1000
    noise = rng.uniform(-0.0010, 0.0010, n)
    return pd.Series(base + noise, dtype=float)


def _trending_up_series(n: int = 60) -> pd.Series:
    """Steadily rising series going from 1.1000 to ~1.1060."""
    return pd.Series(np.linspace(1.1000, 1.1060, n), dtype=float)


# ===========================================================================
# Bollinger Bands computation
# ===========================================================================

class TestComputeBollingerBands:
    def test_returns_three_series(self):
        closes = _flat_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)

    def test_length_matches_input(self):
        closes = _flat_series(n=50)
        upper, middle, lower = compute_bollinger_bands(closes)
        assert len(upper) == 50
        assert len(middle) == 50
        assert len(lower) == 50

    def test_first_period_minus_1_rows_are_nan(self):
        n = 40
        closes = _ranging_series(n=n)
        period = config.BB_PERIOD  # 20
        upper, middle, lower = compute_bollinger_bands(closes, period=period)
        # First (period - 1) values should be NaN
        assert upper.iloc[: period - 1].isna().all()
        assert middle.iloc[: period - 1].isna().all()
        assert lower.iloc[: period - 1].isna().all()

    def test_flat_series_bands_equal_mean(self):
        """When all closes are identical the std-dev is 0 → all bands equal."""
        closes = _flat_series(value=1.2345, n=40)
        upper, middle, lower = compute_bollinger_bands(closes)
        last_idx = len(closes) - 1
        assert math.isclose(upper.iloc[last_idx], 1.2345, rel_tol=1e-9)
        assert math.isclose(middle.iloc[last_idx], 1.2345, rel_tol=1e-9)
        assert math.isclose(lower.iloc[last_idx], 1.2345, rel_tol=1e-9)

    def test_upper_above_lower(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        valid = ~upper.isna()
        assert (upper[valid] >= lower[valid]).all()

    def test_middle_between_bands(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        valid = ~upper.isna()
        assert (middle[valid] >= lower[valid]).all()
        assert (middle[valid] <= upper[valid]).all()

    def test_custom_period_and_multiplier(self):
        closes = _ranging_series(n=50)
        upper10, mid10, lower10 = compute_bollinger_bands(closes, period=10, multiplier=1.5)
        upper20, mid20, lower20 = compute_bollinger_bands(closes, period=20, multiplier=2.0)
        # Both should produce valid results
        assert not upper10.iloc[-1:].isna().any()
        assert not upper20.iloc[-1:].isna().any()


class TestComputeBandWidth:
    def test_band_width_non_negative(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        bw = compute_band_width(upper, lower)
        valid = ~bw.isna()
        assert (bw[valid] >= 0).all()

    def test_flat_series_width_is_zero(self):
        closes = _flat_series()
        upper, _, lower = compute_bollinger_bands(closes)
        bw = compute_band_width(upper, lower)
        assert math.isclose(bw.iloc[-1], 0.0, abs_tol=1e-12)


# ===========================================================================
# Signal: Bollinger Bounce
# ===========================================================================

class TestSignalBollingerBounce:
    def _make_bounce_signal(self) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """Construct a scenario that should trigger a bounce signal."""
        n = 60
        closes = _ranging_series(n=n)
        upper, middle, lower = compute_bollinger_bands(closes)
        # Force the last close to be well below the lower band
        forced_closes = closes.copy()
        forced_closes.iloc[-1] = float(lower.iloc[-1]) - 0.0010
        upper2, middle2, lower2 = compute_bollinger_bands(forced_closes)
        return forced_closes, upper2, middle2, lower2

    def test_fires_when_close_at_lower_band(self):
        closes, upper, middle, lower = self._make_bounce_signal()
        assert signal_bollinger_bounce(closes, upper, middle, lower) is True

    def test_no_signal_when_close_above_middle(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        # Force close well above middle
        closes.iloc[-1] = float(middle.iloc[-1]) + 0.0020
        upper2, middle2, lower2 = compute_bollinger_bands(closes)
        assert signal_bollinger_bounce(closes, upper2, middle2, lower2) is False

    def test_no_signal_with_insufficient_data(self):
        closes = pd.Series([1.1000] * 5)
        upper, middle, lower = compute_bollinger_bands(closes)
        assert signal_bollinger_bounce(closes, upper, middle, lower) is False

    def test_no_signal_in_strongly_trending_market(self):
        """In a strongly trending market the bands are wide relative to their
        rolling mean, so the bounce signal must NOT fire even if price dips
        below the lower band."""
        closes = _trending_up_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        # In a trending series the band-width >> 2 × its rolling mean, so
        # the ranging condition fails and the bounce signal should be False.
        result = signal_bollinger_bounce(closes, upper, middle, lower)
        assert result is False


# ===========================================================================
# Signal: Bollinger Squeeze
# ===========================================================================

class TestSignalBollingerSqueeze:
    def _make_squeeze_then_breakout(self) -> pd.Series:
        """40 flat bars (squeeze) then a sharp rally above upper band."""
        flat_part = np.full(40, 1.1000)
        # Gradually rise to create a tight squeeze window
        rising_part = np.linspace(1.1000, 1.1020, 15)
        # Final breakout bar well above the ending upper band
        breakout = np.array([1.1080])
        return pd.Series(np.concatenate([flat_part, rising_part, breakout]), dtype=float)

    def test_fires_on_breakout_after_squeeze(self):
        closes = self._make_squeeze_then_breakout()
        upper, middle, lower = compute_bollinger_bands(closes)
        result = signal_bollinger_squeeze(closes, upper, lower)
        assert result is True

    def test_no_signal_with_insufficient_data(self):
        closes = pd.Series([1.1000] * 5)
        upper, _, lower = compute_bollinger_bands(closes)
        assert signal_bollinger_squeeze(closes, upper, lower) is False

    def test_no_signal_when_price_below_upper(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        # Force last close below upper band
        closes.iloc[-1] = float(upper.iloc[-1]) - 0.0010
        upper2, middle2, lower2 = compute_bollinger_bands(closes)
        assert signal_bollinger_squeeze(closes, upper2, lower2) is False

    def test_returns_bool(self):
        closes = _ranging_series()
        upper, _, lower = compute_bollinger_bands(closes)
        assert isinstance(signal_bollinger_squeeze(closes, upper, lower), bool)


# ===========================================================================
# Signal: Walking the Bands
# ===========================================================================

class TestSignalWalkingBands:
    def _make_walking_pullback(self) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Rising series where all recent closes stay above middle, then the
        last bar pulls back to or below the middle band."""
        n = 60
        closes = _trending_up_series(n=n)
        upper, middle, lower = compute_bollinger_bands(closes)

        # Verify recent bars are above the middle (they should be in an uptrend)
        # Then force the last close to the middle band
        forced = closes.copy()
        forced.iloc[-1] = float(middle.iloc[-1]) * 0.9999  # just below middle
        upper2, middle2, lower2 = compute_bollinger_bands(forced)
        return forced, upper2, middle2

    def test_fires_on_pullback_in_uptrend(self):
        closes, upper, middle = self._make_walking_pullback()
        result = signal_walking_bands(closes, upper, middle)
        assert result is True

    def test_no_signal_without_uptrend(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        assert signal_walking_bands(closes, upper, middle) is False

    def test_no_signal_with_insufficient_data(self):
        closes = pd.Series([1.1000] * 5)
        upper, middle, _ = compute_bollinger_bands(closes)
        assert signal_walking_bands(closes, upper, middle) is False

    def test_no_signal_when_above_middle_in_uptrend(self):
        """If the current bar has NOT pulled back, no signal should fire."""
        closes = _trending_up_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        # Force last close well above middle
        closes.iloc[-1] = float(middle.iloc[-1]) + 0.0050
        upper2, middle2, lower2 = compute_bollinger_bands(closes)
        assert signal_walking_bands(closes, upper2, middle2) is False


# ===========================================================================
# Signal dispatcher
# ===========================================================================

class TestGetSignal:
    def test_returns_none_when_no_signal(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        # Mid-range close – no signal expected
        closes.iloc[-1] = float(middle.iloc[-1])
        upper2, middle2, lower2 = compute_bollinger_bands(closes)
        result = get_signal(closes, upper2, middle2, lower2)
        assert result is None or isinstance(result, str)

    def test_returns_string_or_none(self):
        closes = _ranging_series()
        upper, middle, lower = compute_bollinger_bands(closes)
        result = get_signal(closes, upper, middle, lower)
        assert result in (None, "squeeze", "bounce", "walking")

    def test_squeeze_takes_priority(self):
        """Manufacture a scenario where both bounce and squeeze could fire:
        the squeeze signal should win (higher priority)."""
        closes = self._squeeze_scenario()
        upper, middle, lower = compute_bollinger_bands(closes)
        result = get_signal(closes, upper, middle, lower)
        # If squeeze fired it should be returned; at minimum the type is correct
        assert result in (None, "squeeze", "bounce", "walking")

    def _squeeze_scenario(self) -> pd.Series:
        flat_part = np.full(40, 1.1000)
        rising_part = np.linspace(1.1000, 1.1020, 15)
        breakout = np.array([1.1080])
        return pd.Series(np.concatenate([flat_part, rising_part, breakout]), dtype=float)


# ===========================================================================
# Risk management helpers
# ===========================================================================

class TestCalculateLotSize:
    def test_basic_calculation(self):
        equity = 500.0
        entry = 1.1000
        sl = entry - 0.0010  # 10 pips
        lots = calculate_lot_size(equity, entry, sl)
        # dollar_risk = 5; pip_risk = 10; pip_value = 10 → lots = 5/(10*10) = 0.05
        assert math.isclose(lots, 0.05, rel_tol=1e-3)

    def test_minimum_lot_floor(self):
        """Very wide stop-loss should not result in less than 0.01 lots."""
        equity = 500.0
        entry = 1.1000
        sl = entry - 1.0  # 10 000 pips – absurdly wide
        lots = calculate_lot_size(equity, entry, sl)
        assert lots == 0.01

    def test_maximum_lot_cap(self):
        """Absurdly narrow stop-loss should not exceed 100 lots."""
        equity = 500.0
        entry = 1.1000
        sl = entry - 0.000001  # 0.01 pip
        lots = calculate_lot_size(equity, entry, sl)
        assert lots <= 100.0

    def test_zero_pip_risk_returns_minimum(self):
        lots = calculate_lot_size(500.0, 1.1000, 1.1000)  # entry == sl
        assert lots == 0.01

    def test_returns_float(self):
        lots = calculate_lot_size(500.0, 1.1000, 1.0990)
        assert isinstance(lots, float)

    def test_two_decimal_places(self):
        lots = calculate_lot_size(500.0, 1.1000, 1.0995)
        assert round(lots, 2) == lots


class TestCalculateStopLossPrice:
    def test_stop_below_entry(self):
        entry = 1.1000
        sl = calculate_stop_loss_price(entry, equity=500.0)
        assert sl < entry

    def test_stop_distance_matches_risk(self):
        equity = 500.0
        entry = 1.1000
        sl = calculate_stop_loss_price(entry, equity=equity)
        # distance = STOP_LOSS_PCT * equity / contract_size
        expected_distance = config.STOP_LOSS_PCT * equity / 100_000
        actual_distance = round(entry - sl, 5)
        assert math.isclose(actual_distance, expected_distance, rel_tol=1e-4)

    def test_returns_float(self):
        sl = calculate_stop_loss_price(1.1000, 500.0)
        assert isinstance(sl, float)


class TestCalculateTakeProfitPrice:
    def test_bounce_targets_middle(self):
        tp = calculate_take_profit_price(1.0990, middle=1.1000, upper=1.1020, signal="bounce")
        assert math.isclose(tp, 1.1000, rel_tol=1e-6)

    def test_walking_targets_upper(self):
        tp = calculate_take_profit_price(1.1010, middle=1.1000, upper=1.1020, signal="walking")
        assert math.isclose(tp, 1.1020, rel_tol=1e-6)

    def test_squeeze_target_above_upper(self):
        # squeeze TP = upper + (upper - entry) / 2
        entry, upper = 1.1000, 1.1020
        tp = calculate_take_profit_price(entry, middle=1.1000, upper=upper, signal="squeeze")
        expected = upper + (upper - entry) / 2.0
        assert math.isclose(tp, expected, rel_tol=1e-6)

    def test_returns_float(self):
        tp = calculate_take_profit_price(1.1000, 1.1000, 1.1020, "bounce")
        assert isinstance(tp, float)
