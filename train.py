from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score

from model_store import save_model
from indicators import add_indicators, FEATURES, READY
from labels import (
    HORIZON_MINUTES,
    MODEL_THRESHOLD,
    TARGET_RETURN,
    add_labels,
    time_split,
)

DATA = Path("data/market.csv")

df = pd.read_csv(DATA)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values(["token_address", "timestamp"])

df = add_indicators(df)
df = add_labels(df, HORIZON_MINUTES, TARGET_RETURN)
df = df[df["price_usd"] > 0]
df = df.dropna(subset=READY + ["future_return"])

if len(df) < 500:
    raise SystemExit(
        f"Only {len(df)} usable rows. Collect substantially more data before training."
    )

train, test, cut = time_split(df, HORIZON_MINUTES)

if train.empty or test.empty:
    raise SystemExit("Not enough time span for a train/test split. Collect longer.")

X_train, y_train = train[FEATURES], train["target"]
X_test, y_test = test[FEATURES], test["target"]

model = HistGradientBoostingClassifier(
    max_iter=300,
    learning_rate=0.05,
    max_leaf_nodes=15,
    l2_regularization=2.0,
    random_state=42,
)
model.fit(X_train, y_train)

proba = model.predict_proba(X_test)[:, 1]
pred = (proba >= MODEL_THRESHOLD).astype(int)

print(f"Horizon: {HORIZON_MINUTES} min | target: {TARGET_RETURN:.0%} | threshold: {MODEL_THRESHOLD}")
print("Rows:", len(df), "| Train:", len(train), "| Test:", len(test))
print("Test period starts:", cut)
print("Positive rate train/test:", round(y_train.mean(), 3), "/", round(y_test.mean(), 3))

if y_test.nunique() > 1:
    print("ROC AUC:", round(roc_auc_score(y_test, proba), 4))

print(classification_report(y_test, pred, zero_division=0))

save_model(
    {
        "model": model,
        "features": FEATURES,
        "threshold": MODEL_THRESHOLD,
        "horizon_minutes": HORIZON_MINUTES,
        "target_return": TARGET_RETURN,
        "test_start": cut,
    }
)
print("Saved models/model.joblib")
