# Solana Meme AI Trader

A paper-first Solana meme-coin scanner and ML research bot.

Pipeline:
1. Discover recent Solana tokens through DEX Screener.
2. Filter by liquidity, volume, transactions and pair age.
3. Record repeated market snapshots to `data/market.csv`.
4. Calculate RSI, EMA, MACD, momentum, volatility and volume features.
5. Create future-return labels (real-time horizon from HORIZON_MINUTES).
6. Train a gradient-boosting classifier.
7. Backtest chronologically.
8. Run a paper-trading loop.

IMPORTANT:
- This is research software, not a profit guarantee.
- Meme coins can go to zero and liquidity can disappear.
- Do not put a main-wallet private key in this project.
- The included live execution path is disabled by default.

## Windows / VS Code setup

Open the project folder in VS Code, then open Terminal:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`.

## Dashboard (see everything in a browser)

```powershell
python dashboard.py
```

Open http://127.0.0.1:8000. It shows collector status, how much data you have, the trained model, live scores per token with mini charts, your last training and backtest output, and your backups. Buttons: Save snapshot, Train model, Run backtest. It cannot trade and never touches a wallet key.

On a phone: do not expose it to the internet. Run it on your PC or VPS and reach it through an SSH tunnel (`ssh -L 8000:127.0.0.1:8000 you@server`, then open http://127.0.0.1:8000 in the phone's SSH app browser or on a laptop) or a private network like Tailscale. If you must bind another address, set `DASH_TOKEN` first and use `--host`; the page asks for the token and sends it only in a header.

## 1. Collect data

Run:

```powershell
python collector.py
```

Let it run for several hours or days. More data is better. The collector writes:

`data/market.csv`

The model cannot be meaningfully trained from a few minutes of data.

Hotkeys (click the terminal first): **S** saves a snapshot of `data/market.csv` and `models/model.joblib` into `backups/<timestamp>/`, **Q** saves and quits. The collector also appends to `data/market.csv` after every scan, so nothing is lost if it crashes. The same keys work in `paper_trader.py`.

## 2. Train

After you have data:

```powershell
python train.py
```

The trained model is written to:

`models/model.joblib`

The script splits by timestamp across all tokens and drops training rows whose label window overlaps the test period. Labels use the price HORIZON_MINUTES of real time later (rows with no snapshot near that time are dropped). HORIZON_MINUTES, TARGET_RETURN and MODEL_THRESHOLD in `.env` are used and saved into the model.

## 3. Backtest

```powershell
python backtest.py
```

This replays only the period AFTER the model's saved test start (same cut-off used in training), holds one position per token at a time, and prints trades, win rate, average/median/worst trade, total PnL (1 unit per trade, no compounding) and max drawdown. Fees and slippage come from `BACKTEST_FEE` and `BACKTEST_SLIPPAGE` in `.env` and are charged on BOTH entry and exit. The backtest starts from `BACKTEST_START_BALANCE`, caps open positions at `BACKTEST_MAX_POSITIONS`, and stakes `BACKTEST_POSITION_FRACTION` of equity per trade. Fewer than 30 trades is not meaningful.

## 4. Paper trader

```powershell
python paper_trader.py
```

The paper trader scans candidates and uses the trained model. It never sends a transaction.

## 5. Optional live execution

Do not enable this until you have independently verified the model, slippage, liquidity filters and execution code.

The original swap script supplied with this project uses `BOT_PRIVATE_KEY` and defaults to dry-run. Keep any private key in an environment variable only and use a dedicated wallet.

## Data source

DEX Screener's API provides Solana token/pair information including price, transactions, volume, liquidity, market cap and pair creation time. Its public API has rate limits, so this project intentionally scans conservatively.

## What the model learns

Target:
"Does this token gain at least TARGET_RETURN within HORIZON_MINUTES?"

Features include:
- RSI 14
- EMA 9/21/50
- MACD
- 1/5/15 minute momentum
- rolling volatility
- volume acceleration
- buy/sell transaction pressure
- liquidity
- volume/liquidity ratio
- pair age

This is not a magic prediction engine. It is a framework for collecting data and testing whether these signals have predictive value.

## Safety notes (patched version)

See CHANGES.md. Only load `models/model.joblib` you trained yourself (model files can run code). Tokens stay tracked after they fail filters so crashes count as losses.
