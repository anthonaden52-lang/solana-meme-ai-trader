"""Survivorship-free tracking: once a token is picked up, keep recording it.

A token found by the scanner stays on the watch list for TRACK_MINUTES even
if it later fails the liquidity/volume filters, so crashes and rugs end up in
the data. If its pair disappears or has no price, a price-0 row is written.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scanner import dead_row, get_pairs_by_address, normalize, scan

TRACK_FILE = Path("data/tracked.json")
TRACK_MINUTES = float(os.getenv("TRACK_MINUTES",
                                str(3 * int(os.getenv("HORIZON_MINUTES", "15")) + 60)))


def load_tracked():
    if TRACK_FILE.exists():
        try:
            return json.loads(TRACK_FILE.read_text())
        except ValueError:
            pass
    return {}


def save_tracked(t):
    TRACK_FILE.parent.mkdir(exist_ok=True)
    tmp = TRACK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(t))
    tmp.replace(TRACK_FILE)


def scan_and_track(tracked):
    """Returns normalized rows for new candidates + every still-tracked token."""
    now = datetime.now(timezone.utc)
    rows = {}
    for p in scan():
        if not p.get("priceUsd"):
            continue
        r = normalize(p)
        rows[r["token_address"]] = r
        t = tracked.setdefault(r["token_address"], {"first_seen": now.isoformat(),
                                                    "pair": r["pair_address"], "symbol": r["symbol"]})
        t["last_pass"] = now.isoformat()

    # drop tokens whose tracking window is over
    for tok in list(tracked):
        if now - datetime.fromisoformat(tracked[tok].get("last_pass", tracked[tok]["first_seen"])) \
                > timedelta(minutes=TRACK_MINUTES):
            del tracked[tok]

    need = {tok: t for tok, t in tracked.items() if tok not in rows}
    if need:
        found = {}
        for p in get_pairs_by_address([t["pair"] for t in need.values()]):
            found[p.get("pairAddress")] = p
        for tok, t in need.items():
            p = found.get(t["pair"])
            if p and p.get("priceUsd") and (p.get("baseToken") or {}).get("address") == tok:
                rows[tok] = normalize(p)
            else:
                rows[tok] = dead_row(tok, t["symbol"], t["pair"])
    return list(rows.values())
