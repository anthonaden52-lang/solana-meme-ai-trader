import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.dexscreener.com"
MIN_LIQ = float(os.getenv("MIN_LIQUIDITY_USD", "25000"))
MIN_VOL = float(os.getenv("MIN_VOLUME_24H_USD", "50000"))
MIN_TXNS = int(os.getenv("MIN_TXNS_24H", "100"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS_PER_SCAN", "25"))

session = requests.Session()
session.headers.update({"User-Agent": "MemeAIResearchBot/1.0"})


def _get(url, tries=5):
    """GET with backoff on HTTP 429 (rate limit) and 5xx."""
    delay = 2.0
    for attempt in range(tries):
        r = session.get(url, timeout=20)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("Retry-After") or delay)
            print(f"[scanner] HTTP {r.status_code}, backing off {wait:.0f}s")
            time.sleep(min(wait, 60))
            delay = min(delay * 2, 60)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    raise requests.HTTPError(f"gave up after {tries} tries: {url}")


def get_latest_profiles():
    return _get(f"{BASE}/token-profiles/latest/v1")


def get_token_pairs(address):
    return _get(f"{BASE}/token-pairs/v1/solana/{address}") or []


def get_pairs_by_address(pair_addresses):
    """Fetch specific pairs (up to 30 per call) regardless of filters."""
    out = []
    for i in range(0, len(pair_addresses), 30):
        chunk = ",".join(pair_addresses[i:i + 30])
        data = _get(f"{BASE}/latest/dex/pairs/solana/{chunk}") or {}
        out.extend(data.get("pairs") or [])
        time.sleep(0.2)
    return out


def num(d, key, default=0):
    try:
        return float(d.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def pick_best_pair(pairs, address):
    good = []
    for p in pairs:
        if p.get("chainId") != "solana":
            continue
        # The token we looked up must be the BASE token, otherwise priceUsd is
        # the price of the other side of the pair (often SOL).
        if (p.get("baseToken") or {}).get("address") != address:
            continue
        liq = num(p.get("liquidity") or {}, "usd")
        vol = num(p.get("volume") or {}, "h24")
        t24 = (p.get("txns") or {}).get("h24") or {}
        txns = num(t24, "buys") + num(t24, "sells")
        if liq >= MIN_LIQ and vol >= MIN_VOL and txns >= MIN_TXNS:
            good.append((p, liq))
    if not good:
        return None
    return max(good, key=lambda x: x[1])[0]


def scan():
    """New candidates that pass the filters right now."""
    profiles = get_latest_profiles()
    candidates = []
    for item in profiles:
        if item.get("chainId") != "solana":
            continue
        address = item.get("tokenAddress")
        if not address:
            continue
        try:
            pair = pick_best_pair(get_token_pairs(address), address)
            if pair:
                candidates.append(pair)
        except requests.RequestException:
            continue
        if len(candidates) >= MAX_TOKENS:
            break
        time.sleep(0.05)
    return candidates


def normalize(pair):
    tx = pair.get("txns") or {}
    vol = pair.get("volume") or {}
    pc = pair.get("priceChange") or {}
    liq = pair.get("liquidity") or {}
    t24 = tx.get("h24") or {}
    t5 = tx.get("m5") or {}

    created = pair.get("pairCreatedAt")
    now = datetime.now(timezone.utc)
    age_min = (now.timestamp() * 1000 - created) / 60000 if created else float("nan")

    return {
        "timestamp": now.isoformat(),
        "token_address": pair.get("baseToken", {}).get("address"),
        "symbol": pair.get("baseToken", {}).get("symbol", ""),
        "price_usd": float(pair.get("priceUsd") or 0),
        "liquidity_usd": float(liq.get("usd") or 0),
        "volume_24h": float(vol.get("h24") or 0),
        "volume_5m": float(vol.get("m5") or 0),
        "buys_5m": float(t5.get("buys") or 0),
        "sells_5m": float(t5.get("sells") or 0),
        "txns_24h": float(t24.get("buys") or 0) + float(t24.get("sells") or 0),
        "price_change_5m": float(pc.get("m5") or 0),
        "price_change_1h": float(pc.get("h1") or 0),
        "pair_age_minutes": max(0, age_min) if age_min == age_min else age_min,
        "pair_address": pair.get("pairAddress", ""),
        "dex": pair.get("dexId", ""),
        "url": pair.get("url", ""),
    }


def dead_row(token_address, symbol, pair_address):
    """A tracked pair that vanished or has no price: recorded as price 0 (total loss)."""
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "token_address": token_address,
            "symbol": symbol, "price_usd": 0.0, "liquidity_usd": 0.0, "volume_24h": 0.0,
            "volume_5m": 0.0, "buys_5m": 0.0, "sells_5m": 0.0, "txns_24h": 0.0,
            "price_change_5m": 0.0, "price_change_1h": 0.0, "pair_age_minutes": float("nan"),
            "pair_address": pair_address, "dex": "", "url": ""}
