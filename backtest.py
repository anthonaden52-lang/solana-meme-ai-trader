import os
from pathlib import Path

import pandas as pd

from indicators import add_indicators, READY
from labels import FEE, SLIPPAGE, add_labels
from model_store import load_model

DATA = Path(os.getenv("BACKTEST_DATA", "data/market.csv"))
START_BALANCE = float(os.getenv("BACKTEST_START_BALANCE", "1000"))
MAX_POSITIONS = int(os.getenv("BACKTEST_MAX_POSITIONS", "3"))
POSITION_FRACTION = float(os.getenv("BACKTEST_POSITION_FRACTION", "0.10"))  # of current equity

bundle = load_model()
model = bundle["model"]
threshold = bundle["threshold"]
features = bundle["features"]
horizon_min = bundle["horizon_minutes"]
test_start = bundle["test_start"]

df = pd.read_csv(DATA)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = add_indicators(df.sort_values(["token_address", "timestamp"]))
df = add_labels(df, horizon_min, bundle["target_return"])
df = df[df["price_usd"] > 0].dropna(subset=READY + ["future_return"])

test = df[df["timestamp"] >= test_start].sort_values("timestamp").copy()
if test.empty:
    raise SystemExit("No test-period rows. Collect more data and retrain.")

test["prob"] = model.predict_proba(test[features])[:, 1]
# Costs are paid on BOTH sides: entry and exit (fee + slippage each time).
side_cost = FEE + SLIPPAGE
test["net_return"] = (1 - side_cost) * (1 + test["future_return"]) * (1 - side_cost) - 1

hold = pd.Timedelta(minutes=horizon_min)
cash = START_BALANCE
open_pos = []          # (exit_time, token, stake, net_return)
trades = []
next_free = {}


def close_until(t):
    global cash
    for p in sorted([p for p in open_pos if p[0] <= t]):
        open_pos.remove(p)
        pnl = p[2] * p[3]
        cash += p[2] + pnl
        trades.append({"exit_time": p[0], "token": p[1], "stake": p[2], "net_return": p[3], "pnl": pnl})


equity_curve = []
for _, r in test[test["prob"] >= threshold].iterrows():
    t, tok = r["timestamp"], r["token_address"]
    close_until(t)
    if len(open_pos) >= MAX_POSITIONS or t < next_free.get(tok, t):
        continue
    equity = cash + sum(p[2] for p in open_pos)
    stake = min(cash, equity * POSITION_FRACTION)
    if stake <= 0:
        continue
    cash -= stake
    open_pos.append((t + hold, tok, stake, r["net_return"]))
    next_free[tok] = t + hold
close_until(pd.Timestamp.max.tz_localize("UTC"))

print(f"Test period: {test['timestamp'].min()} -> {test['timestamp'].max()}")
print(f"Test rows: {len(test)} across {test['token_address'].nunique()} tokens")
print(f"Costs assumed per side: fee {FEE:.1%} + slippage {SLIPPAGE:.1%} (round trip ~{2 * side_cost:.1%})")
print(f"Start balance {START_BALANCE:,.2f}, max {MAX_POSITIONS} open positions, "
      f"{POSITION_FRACTION:.0%} of equity each")
print(f"Baseline (enter every row): avg net {test['net_return'].mean():.2%}")

if not trades:
    print("No trades met the model threshold.")
    raise SystemExit

tr = pd.DataFrame(trades).sort_values("exit_time")
equity = START_BALANCE + tr["pnl"].cumsum()
drawdown = equity / equity.cummax() - 1
print(f"\nTrades: {len(tr)} on {tr['token'].nunique()} tokens")
print(f"Win rate: {(tr['net_return'] > 0).mean():.1%}")
print(f"Average trade: {tr['net_return'].mean():.2%} | median {tr['net_return'].median():.2%} "
      f"| worst {tr['net_return'].min():.2%}")
print(f"Final balance: {equity.iloc[-1]:,.2f} ({equity.iloc[-1] / START_BALANCE - 1:+.1%})")
print(f"Max drawdown: {drawdown.min():.1%}")
if len(tr) < 30:
    print("\nWarning: fewer than 30 trades. Results are not statistically meaningful.")
