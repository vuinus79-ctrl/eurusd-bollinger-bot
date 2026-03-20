# eurusd-bollinger-bot

A **buy-only** Python trading bot for the **EURUSD** pair on the **1-minute**
timeframe, powered by three complementary Bollinger Bands strategies and
connected to **MetaTrader 5**.

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the bot](#running-the-bot)
5. [Running the tests](#running-the-tests)
6. [Strategies](#strategies)
7. [Risk management](#risk-management)
8. [Configuration reference](#configuration-reference-configpy)
9. [Troubleshooting](#troubleshooting)
10. [Disclaimer](#disclaimer)

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **Windows 10 / 11** | The `MetaTrader5` Python package only works on Windows. All strategy logic and tests can be run on any OS. |
| **Python 3.10+** | Download from [python.org](https://www.python.org/downloads/). Tick *"Add Python to PATH"* during installation. |
| **MetaTrader 5** | Free download: <https://www.metatrader5.com/en/download> |
| **Broker account** | Open a **demo** account with any MT5 broker (e.g. IC Markets, Pepperstone, XM, FBS). Demo accounts are free and carry no financial risk. |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/vuinus79-ctrl/eurusd-bollinger-bot.git
cd eurusd-bollinger-bot

# 2. (Recommended) Create an isolated virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux (strategy tests only)

# 3. Install dependencies
pip install -r requirements.txt
```

> **Note:** `MetaTrader5` installs cleanly on Windows only.  On macOS/Linux
> the package install will fail; remove it from `requirements.txt` if you only
> want to run the unit tests on those platforms.

---

## Configuration

Open **`config.py`** in any text editor and fill in your MT5 credentials:

```python
MT5_LOGIN    = 12345678           # Your numeric account number
MT5_PASSWORD = "YourPassword"     # Your account password
MT5_SERVER   = "ICMarketsSC-Demo" # Your broker's server name (see below)
```

### How to find your broker server name

There are two easy ways:

**Option A – MT5 status bar**
> After logging in to MT5, look at the very bottom-left of the terminal window.
> You will see something like `ICMarketsSC-Demo  Connected`.
> The part before *Connected* is your server name.

**Option B – MT5 Options**
> Inside MT5 go to **Tools → Options → Server** tab.
> The server field shows the exact name.

### Optional settings

```python
EQUITY = 500.0   # Adjust if your account balance is different
MT5_PATH = None  # Only needed if MT5 is NOT in the default installation folder
                 # e.g. MT5_PATH = r"C:\MyApps\MT5\terminal64.exe"
```

---

## Running the bot

```bash
python bot.py
```

**What happens when you start it:**

1. The bot validates that all credentials are filled in.  If any are missing it
   prints a clear checklist explaining exactly what to set and where to find it.
2. It connects to MetaTrader 5 and logs in to your account.
3. Every 60 seconds it fetches the latest 1-minute EURUSD bars, evaluates all
   three Bollinger Bands strategies, and places a market buy order when a
   signal fires (provided no position is already open).
4. Press **Ctrl+C** to stop the bot gracefully.

**Sample startup output:**

```
2024-01-15 09:00:00 [INFO] Starting EURUSD Bollinger Bands Bot ...
2024-01-15 09:00:01 [INFO] Connected to MetaTrader 5: ...
2024-01-15 09:00:01 [INFO] --- Tick at 2024-01-15 09:00:01 UTC ---
2024-01-15 09:00:01 [INFO] No signal this bar.
2024-01-15 09:01:01 [INFO] --- Tick at 2024-01-15 09:01:01 UTC ---
2024-01-15 09:01:01 [INFO] Signal detected: bounce
2024-01-15 09:01:01 [INFO] Placing BUY | entry=1.08523 sl=1.08518 tp=1.08531 lots=0.05 signal=bounce
2024-01-15 09:01:01 [INFO] BUY order sent: symbol=EURUSD lots=0.05 sl=1.08518 tp=1.08531 ticket=12345
```

---

## Running the tests

No MetaTrader 5 installation is required to run the tests.

```bash
python -m pytest tests/ -v
```

Expected output: **37 tests passed**.

---

## Strategies

> Signal priority: **Squeeze > Bounce > Walking**.

### 1 · Bollinger Bounce *(range trading)*
| | |
|---|---|
| **Trigger** | Price closes at or below the lower band while the market is in a *sideways* regime (band-width < 2 × its rolling mean). |
| **Target** | Middle band (20-period SMA). |
| **Concept** | Mean reversion – in calm markets price tends to snap back toward the centre. |

### 2 · Bollinger Squeeze *(breakout trading)*
| | |
|---|---|
| **Trigger** | Bands have been tightening (width ≤ 1.2 × recent minimum) and price then closes *above* the upper band. |
| **Target** | Upper band + half the breakout distance (measured-move projection). |
| **Concept** | Low volatility precedes large moves; entering on the expansion gives the best risk/reward. |

### 3 · Walking the Bands *(trend following)*
| | |
|---|---|
| **Trigger** | Price has spent the last 5 bars above the middle band (uptrend confirmed) and the current bar pulls back to touch the middle band. |
| **Target** | Upper band. |
| **Concept** | In strong uptrends, dips to the 20-SMA are re-entry opportunities rather than exit signals. |

---

## Risk management

| Parameter | Value |
|---|---|
| Equity | $500 USD (configurable) |
| Risk per trade | 1 % of equity ($5) |
| Stop-loss | 1 % of equity ($5) – placed below entry |
| Direction | Buy (long) only |
| Max open positions | 1 |

Lot size is calculated with the standard dollar-risk formula:

```
lots = dollar_risk / (pip_risk × pip_value_per_lot)
```

---

## File structure

```
eurusd-bollinger-bot/
├── bot.py           # Main bot: indicators, signals, MT5 integration
├── config.py        # All tunable parameters + credential placeholders
├── requirements.txt # Python dependencies
└── tests/
    └── test_bot.py  # Unit tests (37 tests, no MT5 required)
```

---

## Configuration reference (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `EQUITY` | `500.0` | Reference equity in USD |
| `RISK_PER_TRADE` | `0.01` | Fraction of equity risked per order |
| `STOP_LOSS_PCT` | `0.01` | Fraction of equity for stop-loss distance |
| `SYMBOL` | `"EURUSD"` | Instrument |
| `TIMEFRAME_STR` | `"M1"` | Timeframe (M1, M5, M15, H1) |
| `BB_PERIOD` | `20` | Bollinger Bands lookback window |
| `BB_STD_MULTIPLIER` | `2.0` | Standard-deviation multiplier |
| `SQUEEZE_THRESHOLD` | `1.2` | Squeeze detection sensitivity |
| `TREND_LOOKBACK` | `5` | Bars checked for uptrend confirmation |
| `LOOP_INTERVAL_SECONDS` | `60` | Polling interval |
| `MT5_PATH` | `None` | Path to `terminal64.exe` (None = default) |
| `MT5_LOGIN` | `None` | Your MT5 account number (int) |
| `MT5_PASSWORD` | `None` | Your MT5 password (str) |
| `MT5_SERVER` | `None` | Broker server name (str) |

---

## Troubleshooting

### "MT5 credentials not configured"

You see this message when `MT5_LOGIN`, `MT5_PASSWORD`, or `MT5_SERVER` in
`config.py` are still `None`.  Fill them in as shown in the
[Configuration](#configuration) section above.

### "MT5 initialize() failed"

- Make sure MetaTrader 5 is **installed** on your machine.
- Make sure the MT5 terminal is **not blocked by a firewall**.
- If MT5 is installed in a non-default folder, set `MT5_PATH` to the full
  path of `terminal64.exe`.

### "MT5 login() failed"

- Double-check your account number, password, and server name.
- Verify you can log in manually in the MT5 terminal with the same credentials.
- Some brokers require the server name to include the suffix, e.g.
  `"BrokerName-Live"` vs `"BrokerName-Demo01"`.

### "MetaTrader5 package not available"

- The `MetaTrader5` Python package only works on **Windows**.
- On macOS or Linux you can run all strategy tests (`pytest tests/`) but
  cannot trade live.

### The bot runs but never places an order

- The strategies only fire a buy signal under specific market conditions.
  During low-activity periods no signal may appear for many minutes.
- Check the logs for `No signal this bar.` – this is normal behaviour.
- Make sure the EURUSD symbol is available and not marked as "Offline" in the
  MT5 Market Watch window (View → Market Watch).

---

## Disclaimer

This software is provided for educational purposes only.  
Trading foreign exchange carries significant risk and may not be suitable for
all investors.  Past performance is not indicative of future results.

