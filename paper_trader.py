from pathlib import Path

import pandas as pd

from hotkeys import KeyReader, sleep_with_keys, snapshot
from indicators import add_indicators, window_history, READY
from model_store import MODEL_PATH, load_model
from tracking import load_tracked, save_tracked, scan_and_track

HISTORY = Path("data/paper_history.csv")  # persisted so a restart keeps indicator history

if not MODEL_PATH.exists():
    raise SystemExit("Train a model first: python train.py")

bundle = load_model()
model = bundle["model"]
features = bundle["features"]
threshold = bundle["threshold"]

if HISTORY.exists():
    history = pd.read_csv(HISTORY)
    history["timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
else:
    history = pd.DataFrame()
tracked = load_tracked()

print("PAPER TRADER - no transactions will be sent.  S = save snapshot, Q = quit.")
print("Signals need about 15 minutes of history per token, so expect a quiet start.")


def step():
    """One scan: update history, print top signals."""
    global history
    rows = scan_and_track(tracked)
    save_tracked(tracked)
    if not rows:
        return
    new = pd.DataFrame(rows)
    new["timestamp"] = pd.to_datetime(new["timestamp"], utc=True)
    history = window_history(pd.concat([history, new], ignore_index=True))
    HISTORY.parent.mkdir(exist_ok=True)
    history.to_csv(HISTORY, index=False)

    x = add_indicators(history.copy())
    latest = x.groupby("token_address").tail(1).dropna(subset=READY)
    if latest.empty:
        print("Waiting for more history...")
        return

    latest = latest.copy()
    latest["probability"] = model.predict_proba(latest[features])[:, 1]
    latest = latest.sort_values("probability", ascending=False)

    print("\nTOP SIGNALS")
    for _, r in latest.head(10).iterrows():
        print(f"{r['symbol']:<12} P={r['probability']:.1%} RSI={r['rsi14']:.1f} "
              f"5m={r['return_5']:.2%} liq=${r['liquidity_usd']:,.0f}")

    strong = latest[latest["probability"] >= threshold]
    if not strong.empty:
        print("\nPAPER SIGNAL:", strong.iloc[0]["symbol"])


with KeyReader() as keys:
    while True:
        try:
            step()
            wait = 60
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Paper trader error:", e)
            wait = 15
        if sleep_with_keys(wait, keys):
            break

snapshot()
print("Stopped.")
