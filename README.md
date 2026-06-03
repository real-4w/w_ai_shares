# w_ai_shares
Willem's AI assisted share advisor

w_share_main code supported by Grok.com https://grok.com/share/bGVnYWN5_d3d9c56c-0786-45f8-b9bc-d533225f2fd3

w_ticker code supported by Grok.com https://grok.com/chat/e51999c3-6274-431e-a6ed-7e5c399a4119

## Ticker scripts
- `w_ticker.py` — original version
- `tickerV2.py` — improved 2026 version (thread-safe, efficient scrolling, batch yf.download, hover-pause, CLI flags, argparse, stale-data resilience, etc). Run with `python tickerV2.py --help`
- `tickerV3.py` — **recommended/current version** (further improved). Builds on V2 with standard % change vs previous close (via 5d history), `Quote` dataclass, snapshot+reconcile for safe live add/remove, instant tape updates + N/A placeholders on add/remove, listbox chooser for remove (great for 50+ tickers), separate manual/hover pause states + dynamic menu labels, bottom-dock taskbar margin, flexible YAML loading (list or dict), "Reset to Defaults", immediate display of configured tickers as `SYM: N/A`, refactored fetch helpers + proper logging, early screen geometry fixes, etc. All V2 strengths preserved (efficient move-only animation, batch+fallback, queue/thread safety, etc). Run with `python tickerV3.py --help`

Both V2 and V3 use the same `tickers.yaml` format and can coexist.
