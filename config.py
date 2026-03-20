"""
Configuration settings for the EURUSD Bollinger Bands trading bot.
"""

# --- Account / Risk Settings ---
EQUITY = 500.0            # Starting/reference equity in USD
RISK_PER_TRADE = 0.01     # 1% of equity per order
STOP_LOSS_PCT = 0.01      # 1% of equity as max loss per trade

# --- Instrument Settings ---
SYMBOL = "EURUSD"
TIMEFRAME_STR = "M1"      # 1-minute bars

# --- Bollinger Bands Settings ---
BB_PERIOD = 20            # Lookback window for SMA and std-dev
BB_STD_MULTIPLIER = 2.0   # Number of standard deviations for the bands

# --- Squeeze Detection ---
# A "squeeze" is when the band width drops below this multiple of its
# rolling minimum (e.g., within 120 % of the tightest it has been over
# the last BB_PERIOD bars).
SQUEEZE_THRESHOLD = 1.2

# --- Trend / Walking-the-Bands Settings ---
# Minimum number of consecutive closes above the middle band that define a
# "strong uptrend" for the Walking-the-Bands strategy.
TREND_LOOKBACK = 5        # bars to check for trend confirmation

# --- Loop Settings ---
LOOP_INTERVAL_SECONDS = 60   # check for a new bar every 60 s

# --- MetaTrader 5 Connection ---
# Leave MT5_PATH as None to use the default MT5 installation path.
MT5_PATH = None
MT5_LOGIN = None          # replace with your account number (int)
MT5_PASSWORD = None       # replace with your account password (str)
MT5_SERVER = None         # replace with your broker server name (str)
