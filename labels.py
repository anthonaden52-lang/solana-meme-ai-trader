"""Shared settings, time-based labels, and the chronological split."""
import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

HORIZON_MINUTES = int(os.getenv("HORIZON_MINUTES", "15"))
TARGET_RETURN = float(os.getenv("TARGET_RETURN", "0.10"))
MODEL_THRESHOLD = float(os.getenv("MODEL_THRESHOLD", "0.70"))
# Costs are PER SIDE: charged once on entry and again on exit.
FEE = float(os.getenv("BACKTEST_FEE", "0.005"))
SLIPPAGE = float(os.getenv("BACKTEST_SLIPPAGE", "0.02"))
TEST_FRACTION = 0.20


def _tolerance(horizon_minutes):
    # How far past the exact horizon we accept a price (scans are irregular).
    return pd.Timedelta(minutes=max(1.0, horizon_minutes * 0.2))


def add_labels(df, horizon_minutes=HORIZON_MINUTES, target_return=TARGET_RETURN):
    """Label each row with the token's price `horizon_minutes` of REAL TIME later.

    Uses the first snapshot at or after (timestamp + horizon), within a
    tolerance. Rows with no such snapshot get NaN future_return and must be
    dropped by the caller (they are NOT counted as losers or winners).
    """
    horizon = pd.Timedelta(minutes=horizon_minutes)
    left = df.sort_values("timestamp").copy()
    left["_target_ts"] = left["timestamp"] + horizon

    right = (
        df[["timestamp", "token_address", "price_usd"]]
        .rename(columns={"timestamp": "future_ts", "price_usd": "future_price"})
        .sort_values("future_ts")
    )
    out = pd.merge_asof(
        left,
        right,
        left_on="_target_ts",
        right_on="future_ts",
        by="token_address",
        direction="forward",
        tolerance=_tolerance(horizon_minutes),
    )
    out["future_return"] = out["future_price"] / out["price_usd"] - 1

    # Survivorship fix: if the token stopped appearing (its last snapshot is
    # before the target time) while collection kept going past the target,
    # it vanished -> count it as a total loss instead of dropping the row.
    last_seen = df.groupby("token_address")["timestamp"].max()
    tok_last = out["token_address"].map(last_seen)
    data_end = df["timestamp"].max()
    vanished = (out["future_return"].isna()
                & (tok_last < out["_target_ts"])
                & (data_end > out["_target_ts"] + _tolerance(horizon_minutes)))
    out.loc[vanished, "future_return"] = -1.0
    # Price-0 snapshots (dead pairs, written by tracking.py) also give -100%.
    out["target"] = (out["future_return"] >= target_return).astype(int)
    out.loc[out["price_usd"] <= 0, "future_return"] = float("nan")  # can't enter at price 0
    return out.drop(columns="_target_ts")


def time_split(df, horizon_minutes=HORIZON_MINUTES, test_fraction=TEST_FRACTION):
    """Split by TIMESTAMP across all tokens.

    Train rows whose label window reaches into the test period are dropped
    (embargo), so no training label peeks at test-period prices.
    """
    df = df.sort_values("timestamp")
    cut = df["timestamp"].iloc[int(len(df) * (1 - test_fraction))]
    embargo = pd.Timedelta(minutes=horizon_minutes) + _tolerance(horizon_minutes)
    train = df[df["timestamp"] < cut - embargo]
    test = df[df["timestamp"] >= cut]
    return train, test, cut
