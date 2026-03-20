# eurusd-bollinger-bot

A **buy-only** Python trading bot for the **EURUSD** pair on the **1-minute**
timeframe, powered by three complementary Bollinger Bands strategies and
connected to **MetaTrader 5**.

---

## Strategies

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

> Signal priority: **Squeeze > Bounce > Walking**.

---

## Risk management

| Parameter | Value |
|---|---|
| Equity | $500 USD |
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
├── config.py        # All tunable parameters
├── requirements.txt # Python dependencies
└── tests/
    └── test_bot.py  # Unit tests (37 tests, no MT5 required)
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `MetaTrader5` is only available on **Windows** with MT5 installed.
> All strategy logic and tests run without it.

### 2. Configure credentials

Edit `config.py`:

```python
MT5_LOGIN    = 123456          # your MT5 account number
MT5_PASSWORD = "your_password"
MT5_SERVER   = "YourBroker-Live"
```

### 3. Run the bot

```bash
python bot.py
```

The bot wakes up every 60 seconds, fetches the latest 1-minute EURUSD bars,
evaluates all three strategies, and places a market buy order whenever a
signal fires and no position is already open.

### 4. Run the tests

```bash
python -m pytest tests/ -v
```

---

## Configuration reference (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `EQUITY` | `500.0` | Reference equity in USD |
| `RISK_PER_TRADE` | `0.01` | Fraction of equity risked per order |
| `STOP_LOSS_PCT` | `0.01` | Fraction of equity for stop-loss distance |
| `SYMBOL` | `"EURUSD"` | Instrument |
| `TIMEFRAME_STR` | `"M1"` | Timeframe |
| `BB_PERIOD` | `20` | Bollinger Bands lookback window |
| `BB_STD_MULTIPLIER` | `2.0` | Standard-deviation multiplier |
| `SQUEEZE_THRESHOLD` | `1.2` | Squeeze detection sensitivity |
| `TREND_LOOKBACK` | `5` | Bars checked for uptrend confirmation |
| `LOOP_INTERVAL_SECONDS` | `60` | Polling interval |

---

## Disclaimer

This software is provided for educational purposes only.  
Trading foreign exchange carries significant risk and may not be suitable for
all investors.  Past performance is not indicative of future results.
