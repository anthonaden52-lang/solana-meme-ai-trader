# Changes (one line per review finding)

## swap_bot.py (rebuilt from the PDF with proper indentation)
1. (High #2) Price impact is now read as a positive percent with abs(); `priceImpact` is treated as a percent and `priceImpactPct` as a fraction (x100). Unreadable impact refuses the trade. UNITS MUST BE CONFIRMED against current Jupiter docs.
2. (High #3) Missing router fee, price impact, USD values or slippage threshold now refuse the trade unless --allow-unknown-value is passed.
3. (High #4) New --max-slippage-bps (default 100): refuses if the guaranteed minimum output is more than that below the quote.
4. (High #5) Before signing, the order's inputMint, outputMint, inAmount, taker and outAmount must match the request, or the trade is refused.
5. (Med #7) Every trade is logged to data/trades.jsonl before sending (no keys); timeouts/errors check the chain status, and the next --execute refuses while an earlier trade is unresolved (--ignore-pending after you check).
6. (Med #8) JUPITER_BASE and SOLANA_RPC_URL must be https hosts on an in-code allowlist; decimals are sanity-checked and shown in the quote and the YES prompt.
7. (Med #9) New --max-daily-usd cap (default 100, per UTC day, from the trade log); --yes prints a loud warning.
8. (Low #18) All Jupiter numbers go through float()/to_float() before formatting or comparing.
9. (Low #19) Profane error messages replaced with plain wording.
10. Extra: invalid BOT_PRIVATE_KEY gives a message that never echoes the key; requests don't follow redirects; --selftest now also tests the new checks.

## scanner.py / tracking.py (new) / collector.py / labels.py
11. (Critical #1) Tokens stay tracked (data/tracked.json) for TRACK_MINUTES after they last passed the filters and are re-fetched by pair address; a vanished/priceless pair is written as price 0.
12. (Critical #1) labels.py: a token that stops appearing while collection continues gets future_return = -100% instead of being dropped; price-0 rows are never used as entries.
13. (High #6) scanner.py only accepts pairs whose baseToken is the token looked up.
14. (Low #15) scanner.py backs off and retries on HTTP 429/5xx (honours Retry-After).

## backtest.py / labels.py / .env.example
15. (Med #10) Fee and slippage are charged on entry AND exit; defaults now 0.5% fee + 2% slippage per side.
16. (Med #13) Backtest uses a starting balance, a max number of open positions and a fixed fraction of equity per trade; reports final balance and % drawdown.

## indicators.py
17. (Med #11) return_1/5/15 are now over real minutes (price at or before t-n minutes), and indicators restart after a gap longer than GAP_MINUTES.
18. (Med #12) One history window (HISTORY_ROWS=300 via window_history) used by paper trader and dashboard; long enough that EMAs match training.

## paper_trader.py
19. (Med #12) History is saved to data/paper_history.csv and reloaded on restart; uses the same tracking as the collector.

## model_store.py (new) / train.py / backtest.py / paper_trader.py / dashboard.py
20. (Med #14) Models load only from models/model.joblib and only if its SHA-256 matches models/model.sha256 written by train.py, with a warning that model files can run code.

## dashboard.py
21. (Low #16) Token is accepted only in the X-Token header; the page prompts for it (kept in sessionStorage) and the startup line no longer prints it.

## .gitignore (new) / hotkeys.py / README.md
22. (Low #17) .gitignore excludes .env, key files, data/, models/, backups/.
23. hotkeys snapshot also saves model hash, tracked list and trade log; README updated.
