import os

import numpy as np
import pandas as pd

# A gap longer than this between two snapshots of a token starts a new
# "segment": indicators restart instead of bridging hours of missing data.
GAP_MINUTES = float(os.getenv("GAP_MINUTES", "5"))

# Rows of history per token used at inference time (paper trader, dashboard).
# Training computes indicators on the full segment; with 300 rows the slowest
# EMA (span 50) keeps < 0.001% weight from older rows, so features match.
HISTORY_ROWS = 300

RETURN_WINDOWS_MIN = (1, 5, 15)


def window_history(df):
    """The ONE history window used everywhere features are computed live."""
    return (df.sort_values(["token_address", "timestamp"])
              .groupby("token_address", group_keys=False).tail(HISTORY_ROWS))


def _time_return(df, minutes):
    """Return vs the last price at or before (t - minutes), same token+segment."""
    tol = pd.Timedelta(minutes=max(1.0, minutes * 0.5))
    left = df[["timestamp", "seg"]].copy()
    left["_i"] = np.arange(len(df))
    left["_t"] = left["timestamp"] - pd.Timedelta(minutes=minutes)
    right = df[["timestamp", "seg", "price_usd"]].rename(columns={"timestamp": "_t", "price_usd": "_p"})
    m = pd.merge_asof(left.sort_values("_t"), right.sort_values("_t"), on="_t", by="seg",
                      direction="backward", tolerance=tol).sort_values("_i")
    return df["price_usd"].to_numpy() / m["_p"].to_numpy() - 1


def add_indicators(df):
    df = df.sort_values(["token_address", "timestamp"]).copy()
    gap = df.groupby("token_address")["timestamp"].diff() > pd.Timedelta(minutes=GAP_MINUTES)
    new_tok = df["token_address"] != df["token_address"].shift()
    df["seg"] = (gap | new_tok).cumsum()
    g = df.groupby("seg", group_keys=False)

    def ema(s, n):
        return s.ewm(span=n, adjust=False).mean()

    for n in (9, 21, 50, 12, 26):
        df[f"ema{n}"] = g["price_usd"].transform(lambda s, n=n: ema(s, n))
    df["macd"] = df["ema12"] - df["ema26"]
    df["macd_signal"] = df.groupby("seg")["macd"].transform(lambda s: ema(s, 9))

    delta = g["price_usd"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(df["seg"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    avg_loss = loss.groupby(df["seg"]).transform(lambda s: s.rolling(14, min_periods=14).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain == 0)), 50.0)
    df["rsi14"] = rsi

    # Returns over REAL time (minutes), not over a number of scans.
    for n in RETURN_WINDOWS_MIN:
        df[f"return_{n}"] = _time_return(df, n)

    df["volatility_15"] = df.groupby("seg")["return_1"].transform(
        lambda s: s.rolling(15, min_periods=10).std())
    df["volume_change_5"] = g["volume_5m"].pct_change(5, fill_method=None)
    df["buy_sell_ratio"] = (df["buys_5m"] + 1) / (df["sells_5m"] + 1)
    df["volume_liquidity"] = df["volume_24h"] / df["liquidity_usd"].replace(0, np.nan)
    df["ema_spread"] = (df["ema9"] - df["ema21"]) / df["price_usd"].replace(0, np.nan)
    df["macd_spread"] = df["macd"] - df["macd_signal"]

    df[FEATURES] = df[FEATURES].replace([np.inf, -np.inf], np.nan)
    # A price-0 row (dead/vanished pair) is never a valid entry.
    df.loc[df["price_usd"] <= 0, READY] = np.nan
    return df


FEATURES = [
    "rsi14", "ema_spread", "macd_spread", "return_1", "return_5", "return_15",
    "volatility_15", "volume_change_5", "buy_sell_ratio", "volume_liquidity",
    "liquidity_usd", "volume_24h", "txns_24h", "pair_age_minutes",
]

# A row is usable once enough history exists for the slow indicators.
READY = ["rsi14", "return_15"]
