"""
Configuration settings for the EURUSD Bollinger Bands trading bot.

HOW TO FILL IN YOUR CREDENTIALS
---------------------------------
1. Open MetaTrader 5 -> File -> Open an Account (or log in to an existing one).
2. Your login number is the numeric account ID shown in the top-left of MT5.
3. Your server name is shown in the connection status bar at the bottom of MT5
   (e.g. "ICMarketsSC-Demo", "Pepperstone-Demo01", "XM-Real15", etc.).
   You can also find it at: Tools -> Options -> Server tab.
4. MT5_PATH is only needed if MT5 is installed in a non-default directory.
   Leave it as None for a standard installation.
"""

# --- Account / Risk Settings ---
EQUITY = 500.0            # Starting/reference equity in USD
RISK_PER_TRADE = 0.01     # 1% of equity per order  (fraction, not percent)
STOP_LOSS_PCT = 0.01      # 1% of equity as max loss per trade (fraction)

# --- Instrument Settings ---
SYMBOL = "EURUSD"
TIMEFRAME_STR = "M1"      # 1-minute bars (supported: M1, M5, M15, H1)

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

# ---------------------------------------------------------------------------
# MetaTrader 5 Connection
# ---------------------------------------------------------------------------
# IMPORTANT: replace the None values below with your real credentials before
# running the bot.  See the docstring at the top of this file for guidance.
# ---------------------------------------------------------------------------

# Full path to terminal64.exe - leave None for default installation:
#   C:\Program Files\MetaTrader 5\terminal64.exe
MT5_PATH = None

# Your numeric MT5 account number (int), e.g.:  MT5_LOGIN = 12345678
MT5_LOGIN = None

# Your account password (str), e.g.:  MT5_PASSWORD = "MySecretPass1!"
MT5_PASSWORD = None

# Broker server name (str), e.g.:  MT5_SERVER = "ICMarketsSC-Demo"
# Find it in MT5 -> bottom status bar, or Tools -> Options -> Server tab.
MT5_SERVER = None
