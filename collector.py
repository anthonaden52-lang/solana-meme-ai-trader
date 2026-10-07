import csv
import os
from pathlib import Path

from hotkeys import KeyReader, sleep_with_keys, snapshot
from tracking import load_tracked, save_tracked, scan_and_track

OUT = Path("data/market.csv")
OUT.parent.mkdir(exist_ok=True)

FIELDS = [
    "timestamp", "token_address", "symbol", "price_usd", "liquidity_usd",
    "volume_24h", "volume_5m", "buys_5m", "sells_5m", "txns_24h",
    "price_change_5m", "price_change_1h", "pair_age_minutes",
    "pair_address", "dex", "url",
]

interval = int(os.getenv("SCAN_INTERVAL", "60"))


def write_rows(rows):
    exists = OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(rows)


print("Starting collector.  Press S = save snapshot, Q = save and quit.")
print(f"Writing to {OUT} (tokens stay tracked after they fail filters, so crashes are recorded)")

tracked = load_tracked()
with KeyReader() as keys:
    while True:
        try:
            rows = scan_and_track(tracked)
            save_tracked(tracked)
            write_rows(rows)
            dead = sum(1 for r in rows if r["price_usd"] <= 0)
            print(f"Collected {len(rows)} rows ({len(tracked)} tracked, {dead} dead/vanished).")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Collector error:", e)
        if sleep_with_keys(interval, keys):
            break

snapshot()
print("Stopped.")
