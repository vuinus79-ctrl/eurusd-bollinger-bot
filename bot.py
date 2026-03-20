"""
EURUSD Bollinger Bands Trading Bot
===================================
Buy-only bot trading the EURUSD pair on the 1-minute timeframe using three
complementary Bollinger Bands strategies:

1. **Bollinger Bounce** (range trading)
   - Trigger : price touches / crosses below the lower band in a sideways market.
   - Target  : middle band (20-period SMA).
   - Stop    : 1 % of equity below the entry price.

2. **Bollinger Squeeze** (breakout trading)
   - Trigger : band width is at a recent minimum (squeeze), then price closes
               *above* the upper band on an expanding move.
   - Target  : upper band + (upper − lower) / 2  (measured-move projection).
   - Stop    : 1 % of equity below the entry price.

3. **Walking the Bands** (trend following)
   - Trigger : price has been riding the upper band for several bars
               (uptrend) and pulls back to touch the middle band.
   - Target  : upper band.
   - Stop    : 1 % of equity below the entry price.

Risk rules
----------
- Equity             : $500 USD (configurable in config.py).
- Risk per trade     : 1 % of equity  → $5 per order.
- Stop-loss per trade: 1 % of equity  → $5 maximum loss.
- Only one open position at a time.
- Buy (long) orders only.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

import config

# ---------------------------------------------------------------------------
# Optional MetaTrader5 import – the module is only available on Windows with
# MT5 installed.  The rest of the bot logic (strategy signals, sizing, …) is
# fully testable without it.
# ---------------------------------------------------------------------------
try:
    import MetaTrader5 as mt5  # type: ignore
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# Indicator helpers
# ===========================================================================

def compute_bollinger_bands(
    closes: pd.Series,
    period: int = config.BB_PERIOD,
    multiplier: float = config.BB_STD_MULTIPLIER,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (upper, middle, lower) Bollinger Bands for a closing-price Series."""
    middle = closes.rolling(window=period).mean()
    std = closes.rolling(window=period).std(ddof=0)
    upper = middle + multiplier * std
    lower = middle - multiplier * std
    return upper, middle, lower


def compute_band_width(upper: pd.Series, lower: pd.Series) -> pd.Series:
    """Band-width as a fraction of the middle band, used for squeeze detection."""
    return upper - lower


# ===========================================================================
# Signal generators
# ===========================================================================

def signal_bollinger_bounce(
    closes: pd.Series,
    upper: pd.Series,
    middle: pd.Series,
    lower: pd.Series,
) -> bool:
    """
    Bollinger Bounce – buy signal.

    Conditions (checked on the *last completed* bar):
    - The market is not in a strong trend: the distance between upper and
      lower bands is not unusually large (band-width < 2 × its own rolling
      mean over ``BB_PERIOD`` bars).
    - The closing price is at or below the lower band.
    """
    if len(closes) < config.BB_PERIOD:
        return False

    bw = compute_band_width(upper, lower)
    bw_mean = bw.rolling(window=config.BB_PERIOD).mean()

    last_close = closes.iloc[-1]
    last_lower = lower.iloc[-1]
    last_bw = bw.iloc[-1]
    last_bw_mean = bw_mean.iloc[-1]

    if pd.isna(last_lower) or pd.isna(last_bw_mean):
        return False

    # Sideways condition: band-width below twice its rolling average
    is_ranging = last_bw < 2.0 * last_bw_mean
    # Touch condition: close ≤ lower band
    touches_lower = last_close <= last_lower

    return bool(is_ranging and touches_lower)


def signal_bollinger_squeeze(
    closes: pd.Series,
    upper: pd.Series,
    lower: pd.Series,
) -> bool:
    """
    Bollinger Squeeze – buy-breakout signal.

    Conditions (checked on the *last completed* bar):
    - Band-width is within ``SQUEEZE_THRESHOLD`` × its rolling minimum over
      the last ``BB_PERIOD`` bars (i.e., the bands have been squeezing).
    - The closing price breaks *above* the upper band (bullish breakout).
    """
    if len(closes) < config.BB_PERIOD:
        return False

    bw = compute_band_width(upper, lower)
    bw_min = bw.rolling(window=config.BB_PERIOD).min()

    last_close = closes.iloc[-1]
    last_upper = upper.iloc[-1]
    last_bw = bw.iloc[-1]
    last_bw_min = bw_min.iloc[-1]

    if pd.isna(last_upper) or pd.isna(last_bw_min):
        return False

    # Breakout condition: price closes above the upper band
    breaks_upper = last_close > last_upper

    # Squeeze condition: bandwidth is near (or expanding from) its recent minimum.
    # When bw_min == 0, bands were flat and are now expanding – the most extreme
    # squeeze scenario; treat the condition as met whenever bw > 0.
    if last_bw_min == 0:
        in_squeeze = last_bw > 0
    else:
        in_squeeze = last_bw <= config.SQUEEZE_THRESHOLD * last_bw_min

    return bool(in_squeeze and breaks_upper)


def signal_walking_bands(
    closes: pd.Series,
    upper: pd.Series,
    middle: pd.Series,
) -> bool:
    """
    Walking the Bands – trend-following buy signal.

    Conditions (checked on the *last completed* bar):
    - A strong uptrend is active: the last ``TREND_LOOKBACK`` closes have
      each been above the middle band (20-period SMA).
    - The current bar pulls back to touch the middle band (close ≤ middle),
      offering a re-entry at a favourable price.
    """
    lookback = config.TREND_LOOKBACK
    if len(closes) < config.BB_PERIOD + lookback:
        return False

    recent_closes = closes.iloc[-(lookback + 1):-1]  # bars before last
    recent_middle = middle.iloc[-(lookback + 1):-1]

    if recent_middle.isna().any():
        return False

    # All recent closes above middle band → uptrend confirmation
    uptrend = bool((recent_closes > recent_middle).all())

    last_close = closes.iloc[-1]
    last_middle = middle.iloc[-1]

    if pd.isna(last_middle):
        return False

    # Pullback: latest close touches (≤) the middle band
    pullback_to_middle = last_close <= last_middle

    return bool(uptrend and pullback_to_middle)


def get_signal(
    closes: pd.Series,
    upper: pd.Series,
    middle: pd.Series,
    lower: pd.Series,
) -> Optional[str]:
    """
    Evaluate all three strategies and return the name of the first triggered
    signal, or ``None`` if no signal fires.

    Priority: Squeeze > Bounce > Walking.
    """
    if signal_bollinger_squeeze(closes, upper, lower):
        return "squeeze"
    if signal_bollinger_bounce(closes, upper, middle, lower):
        return "bounce"
    if signal_walking_bands(closes, upper, middle):
        return "walking"
    return None


# ===========================================================================
# Position-sizing & stop-loss helpers
# ===========================================================================

def calculate_lot_size(
    equity: float,
    entry_price: float,
    stop_loss_price: float,
    contract_size: float = 100_000,
) -> float:
    """
    Calculate the lot size so that the monetary risk (entry − stop) equals
    ``RISK_PER_TRADE × equity``.

    For EURUSD the P&L per pip for 1 standard lot is $10 (pip = 0.0001).
    The formula used here is the more general dollar-risk approach:

        lots = dollar_risk / (pip_risk × pip_value_per_lot)

    where ``pip_value_per_lot = contract_size * 0.0001``.

    The result is clipped to [0.01, 100] lots and rounded to 2 decimal places
    (standard MT5 step size).
    """
    dollar_risk = equity * config.RISK_PER_TRADE          # e.g. $5
    pip_risk = abs(entry_price - stop_loss_price) / 0.0001  # in pips
    pip_value_per_lot = contract_size * 0.0001             # $10 for EURUSD

    if pip_risk <= 0 or pip_value_per_lot <= 0:
        return 0.01

    lots = dollar_risk / (pip_risk * pip_value_per_lot)
    lots = max(0.01, min(100.0, round(lots, 2)))
    return lots


def calculate_stop_loss_price(entry_price: float, equity: float) -> float:
    """
    Return a stop-loss price that limits the loss to ``STOP_LOSS_PCT × equity``
    (i.e. 1 % of equity, e.g. $5 on a $500 account).

    The distance is converted from a dollar amount to a price distance using
    the standard EURUSD pip value for 1 micro-lot (0.01 lots).

    For simplicity the stop is placed ``STOP_LOSS_PCT * equity`` *price units*
    below the entry, which is a conservative approximation that works
    regardless of exact lot size.
    """
    stop_distance = equity * config.STOP_LOSS_PCT / 100_000  # in price units
    return round(entry_price - stop_distance, 5)


def calculate_take_profit_price(
    entry_price: float,
    middle: float,
    upper: float,
    signal: str,
) -> float:
    """
    Return a take-profit price based on the active strategy.

    - bounce   : target the middle band.
    - squeeze  : target upper + (upper − entry) / 2  (measured-move).
    - walking  : target the upper band.
    """
    if signal == "bounce":
        return round(middle, 5)
    if signal == "squeeze":
        return round(upper + (upper - entry_price) / 2.0, 5)
    # walking
    return round(upper, 5)


# ===========================================================================
# MetaTrader 5 integration
# ===========================================================================

def mt5_connect() -> bool:
    """Initialise and log in to MetaTrader 5.  Returns True on success."""
    if not MT5_AVAILABLE:
        logger.warning("MetaTrader5 package not available – skipping connection.")
        return False

    init_kwargs: dict = {}
    if config.MT5_PATH:
        init_kwargs["path"] = config.MT5_PATH

    if not mt5.initialize(**init_kwargs):
        logger.error("MT5 initialize() failed: %s", mt5.last_error())
        return False

    if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
        authorised = mt5.login(
            config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        if not authorised:
            logger.error("MT5 login() failed: %s", mt5.last_error())
            mt5.shutdown()
            return False

    logger.info("Connected to MetaTrader 5: %s", mt5.terminal_info())
    return True


def mt5_get_bars(symbol: str, timeframe_str: str, count: int) -> Optional[pd.DataFrame]:
    """
    Fetch the last ``count`` completed bars from MT5 and return a DataFrame
    with columns: time, open, high, low, close, tick_volume.
    """
    if not MT5_AVAILABLE or mt5 is None:
        return None

    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
    }
    tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_M1)

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning("No bars returned for %s / %s", symbol, timeframe_str)
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df


def mt5_has_open_position(symbol: str) -> bool:
    """Return True if there is already an open position for *symbol*."""
    if not MT5_AVAILABLE or mt5 is None:
        return False
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0


def mt5_send_buy_order(
    symbol: str,
    lots: float,
    stop_loss: float,
    take_profit: float,
    comment: str = "",
) -> Optional[object]:
    """
    Send a market buy order.  Returns the order result object or None on failure.
    """
    if not MT5_AVAILABLE or mt5 is None:
        logger.warning("MT5 not available – order not sent.")
        return None

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logger.error("Cannot get tick for %s", symbol)
        return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "sl": stop_loss,
        "tp": take_profit,
        "deviation": 10,
        "magic": 20240101,
        "comment": comment[:31],  # MT5 max comment length
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error("order_send() failed: retcode=%s, comment=%s", result.retcode, result.comment)
        return None

    logger.info(
        "BUY order sent: symbol=%s lots=%.2f sl=%.5f tp=%.5f ticket=%s",
        symbol, lots, stop_loss, take_profit, result.order,
    )
    return result


# ===========================================================================
# Main bot loop
# ===========================================================================

def run_once(equity: float = config.EQUITY) -> Optional[str]:
    """
    Execute one iteration of the trading loop:

    1. Fetch the latest bars from MT5.
    2. Compute Bollinger Bands.
    3. Evaluate buy signals.
    4. If a signal fires and no position is open, place a buy order.

    Returns the signal name that fired, or None.

    This function is designed to be callable from tests (with mocked MT5
    data) as well as from the live loop.
    """
    bars = mt5_get_bars(config.SYMBOL, config.TIMEFRAME_STR, count=config.BB_PERIOD + 50)
    if bars is None or len(bars) < config.BB_PERIOD:
        logger.warning("Insufficient bar data; skipping this iteration.")
        return None

    closes = bars["close"]
    upper, middle, lower = compute_bollinger_bands(closes)

    signal = get_signal(closes, upper, middle, lower)
    if signal is None:
        logger.debug("No signal this bar.")
        return None

    logger.info("Signal detected: %s", signal)

    if mt5_has_open_position(config.SYMBOL):
        logger.info("Position already open – skipping new entry.")
        return signal

    entry_price = closes.iloc[-1]
    sl_price = calculate_stop_loss_price(entry_price, equity)
    tp_price = calculate_take_profit_price(
        entry_price, float(middle.iloc[-1]), float(upper.iloc[-1]), signal
    )
    lots = calculate_lot_size(equity, entry_price, sl_price)

    logger.info(
        "Placing BUY | entry=%.5f sl=%.5f tp=%.5f lots=%.2f signal=%s",
        entry_price, sl_price, tp_price, lots, signal,
    )
    mt5_send_buy_order(config.SYMBOL, lots, sl_price, tp_price, comment=f"BB_{signal}")
    return signal


def run_bot() -> None:
    """
    Continuously run the trading bot, checking for a new 1-minute bar on
    every ``LOOP_INTERVAL_SECONDS`` tick.
    """
    logger.info("Starting EURUSD Bollinger Bands Bot …")

    if not mt5_connect():
        logger.warning(
            "MetaTrader 5 connection not established.  "
            "Set MT5_LOGIN / MT5_PASSWORD / MT5_SERVER in config.py and "
            "run on a Windows machine with MT5 installed."
        )
        return

    try:
        while True:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info("--- Tick at %s ---", now)
            run_once()
            time.sleep(config.LOOP_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        if MT5_AVAILABLE and mt5 is not None:
            mt5.shutdown()
            logger.info("MT5 connection closed.")


if __name__ == "__main__":
    run_bot()
