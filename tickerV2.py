#!/usr/bin/env python3
"""
tickerV2.py - Improved scrolling stock ticker tape (tkinter + yfinance)

This is an improved version of the original ticker script (w_ticker.py).
Key improvements:
- Thread-safe UI: all Tkinter calls from main thread via queue polling.
- Efficient animation: create canvas items ONLY when data changes (~60s).
  Uses canvas.move() + logical offset wrap for smooth  seamless infinite scroll.
  ~100x less object churn than v1 (no delete/create 50x/sec).
- Batch fetching: single yf.download() call for all symbols (much faster for 60+ tickers).
- Stale data resilience: on transient errors keeps last good prices instead of "No data".
- No code duplication for rendering.
- Constants for easy tuning (speed, colors, fonts, intervals).
- argparse support: --config, --dock, --speed, --interval, --height.
- UX: mouse hover pauses scroll, menu has "Refresh Now", "Pause/Resume", "List Tickers".
- Robust config (safe_load, error recovery), interruptible background thread.
- Cleaner structure, better naming, basic logging to console on errors.
- Dock position CLI override respected (doesn't get overwritten by yaml).

Usage:
  python tickerV2.py
  python tickerV2.py --dock bottom --speed 2.0 --config my_tickers.yaml

Requirements: yfinance pandas pyyaml (tkinter is stdlib)
  pip install yfinance pyyaml pandas

Original file w_ticker.py is preserved unchanged.
"""

import argparse
import os
import queue
import threading
import time
from tkinter import simpledialog, messagebox
import tkinter as tk

import pandas as pd
import yaml
import yfinance as yf


# ----------------------------- Tunable Constants -----------------------------
DEFAULT_YAML = "tickers.yaml"
DEFAULT_DOCK = "top"
WINDOW_HEIGHT = 30
FONT = ("Consolas", 11)
BG_COLOR = "#0a0a0a"
SCROLL_SPEED = 1.8          # pixels per animation frame
FRAME_INTERVAL_MS = 22      # ~45 fps - smooth but not CPU heavy
FETCH_INTERVAL_SEC = 60
SPACER_PX = 32
GREEN = "#00ff9f"
RED = "#ff6666"
GRAY = "#888888"
WHITE = "#cccccc"
LOADING_COLOR = "#ffcc66"
SEPARATOR = "•"


class TickerTape:
    """Borderless always-on-top scrolling ticker tape."""

    def __init__(
        self,
        root: tk.Tk,
        yaml_file: str = DEFAULT_YAML,
        dock_position: str | None = None,
        scroll_speed: float = SCROLL_SPEED,
        fetch_interval: int = FETCH_INTERVAL_SEC,
        window_height: int = WINDOW_HEIGHT,
    ):
        self.root = root
        self.yaml_file = yaml_file
        self._cli_dock = dock_position
        self.dock_position = dock_position or DEFAULT_DOCK
        self.scroll_speed = float(scroll_speed)
        self.fetch_interval = int(fetch_interval)
        self.window_height = int(window_height)

        # Screen / geometry
        self.screen_width = max(800, self.root.winfo_screenwidth())
        self.screen_height = self.root.winfo_screenheight()

        # State
        self.tickers: list[str] = ["^GSPC", "^AXJO", "^NZ50"]
        self.ticker_data: list[tuple] = []
        self.content_width: float = 0.0
        self.offset: float = 0.0
        self.paused: bool = False

        # Threading & comms (all Tk ops stay on main thread)
        self.stop_event = threading.Event()
        self.force_refresh = threading.Event()
        self.data_queue: queue.Queue = queue.Queue(maxsize=8)
        self.data_lock = threading.Lock()

        # UI setup
        self._setup_window()
        self._build_canvas()
        self._build_menu()
        self._bind_events()

        # Load config (CLI dock wins)
        self.load_config()

        # Final geometry
        self.update_geometry()

        # Start background + animation
        self._start_background_thread()
        self._schedule_queue_drain()
        self.animate()

    # --------------------------- Window & UI ---------------------------
    def _setup_window(self):
        self.root.title("Stock Ticker V2")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg=BG_COLOR)
        # Prevent accidental close issues
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self.root,
            bg=BG_COLOR,
            highlightthickness=0,
            height=self.window_height,
        )
        self.canvas.pack(fill="both", expand=True)

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Add Ticker", command=self.add_ticker)
        self.menu.add_command(label="Remove Ticker", command=self.remove_ticker)
        self.menu.add_separator()
        self.menu.add_command(label="Refresh Now", command=self._force_refresh)
        self.menu.add_command(label="Pause / Resume Scroll", command=self._toggle_pause)
        self.menu.add_command(label="List Tickers", command=self._show_ticker_list)
        self.menu.add_separator()
        self.menu.add_command(label="Dock to Top", command=lambda: self.set_dock_position("top"))
        self.menu.add_command(label="Dock to Bottom", command=lambda: self.set_dock_position("bottom"))
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)

    def _bind_events(self):
        # Context menu
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<Button-3>", self.show_context_menu)
        # Hover pause (great UX for tickers)
        self.canvas.bind("<Enter>", lambda e: setattr(self, "paused", True))
        self.canvas.bind("<Leave>", lambda e: setattr(self, "paused", False))
        # Keyboard convenience (when focused)
        self.root.bind("<Escape>", lambda e: self.exit_app())
        self.root.bind("<space>", lambda e: self._toggle_pause())
        self.root.bind("<F5>", lambda e: self._force_refresh())

    # --------------------------- Config ---------------------------
    def load_config(self):
        """Load tickers + dock from YAML. CLI dock takes precedence."""
        if not os.path.exists(self.yaml_file):
            return
        try:
            with open(self.yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data.get("tickers"), list):
                loaded = []
                for t in data["tickers"]:
                    if t:
                        s = str(t).strip().upper()
                        if s and s not in loaded:
                            loaded.append(s)
                if loaded:
                    self.tickers = loaded
            if "dock_position" in data and not self._cli_dock:
                pos = str(data["dock_position"]).lower()
                if pos in ("top", "bottom"):
                    self.dock_position = pos
        except Exception as e:
            print(f"[tickerV2] Config load warning ({self.yaml_file}): {e}")

    def save_config(self):
        try:
            with open(self.yaml_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    {
                        "tickers": self.tickers,
                        "dock_position": self.dock_position,
                    },
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                )
        except Exception as e:
            print(f"[tickerV2] Config save failed: {e}")

    def update_geometry(self):
        y = 0 if self.dock_position == "top" else max(0, self.screen_height - self.window_height)
        self.root.geometry(f"{self.screen_width}x{self.window_height}+0+{y}")
        self.root.update_idletasks()

    def set_dock_position(self, position: str):
        if position not in ("top", "bottom") or position == self.dock_position:
            return
        self.dock_position = position
        self.update_geometry()
        self.save_config()
        messagebox.showinfo("Ticker", f"Docked to {position}.", parent=self.root)

    # --------------------------- Data Fetch (background) ---------------------------
    def _perform_fetch(self) -> list[tuple]:
        """Return list of (symbol, price|None, change|None).

        Strategy:
        - Use batch download with explicit group_by='ticker' (works across yf versions).
        - For any symbols that come back empty/NaN (common with large lists or certain .NZ stocks),
          fall back to individual Ticker.history() calls.
        - Always preserve previous good values on transient failures.
        """
        if not self.tickers:
            return []

        # Previous good values (for stale fallback)
        with self.data_lock:
            prev_map = {sym: (p, c) for sym, p, c in self.ticker_data if p is not None}

        batch_df = None
        try:
            batch_df = yf.download(
                tickers=self.tickers,
                period="1d",
                progress=False,
                group_by="ticker",   # Force classic (ticker, field) column structure - critical for yf 1.x / pandas 3
                timeout=25,
            )
        except Exception as e:
            print(f"[tickerV2] yfinance batch download error: {e}")

        # Build results, starting with batch where possible
        results: dict[str, tuple] = {}
        batch_success = 0
        still_missing: list[str] = []

        if batch_df is not None and not batch_df.empty:
            is_multi = isinstance(getattr(batch_df, "columns", None), pd.MultiIndex)
            for symbol in self.tickers:
                price = change = None
                try:
                    if is_multi:
                        # Classic structure after group_by='ticker': top level is the symbol
                        if symbol in batch_df.columns.get_level_values(0):
                            sym_df = batch_df[symbol].dropna(how="all")
                        else:
                            sym_df = pd.DataFrame()
                    else:
                        # Single-ticker case (rare here)
                        sym_df = batch_df.dropna(how="all") if len(self.tickers) <= 1 else pd.DataFrame()

                    if not sym_df.empty and "Close" in sym_df.columns and "Open" in sym_df.columns:
                        c = sym_df["Close"].iloc[-1]
                        o = sym_df["Open"].iloc[0]
                        if pd.notna(c) and pd.notna(o) and float(o) != 0:
                            price = round(float(c), 2)
                            change = round((float(c) - float(o)) / float(o) * 100.0, 2)
                except Exception:
                    pass

                if price is not None:
                    results[symbol] = (price, change)
                    batch_success += 1
                else:
                    still_missing.append(symbol)

        # Fallback: individual fetches (parallel) for anything the batch missed.
        # Large lists (50-60+ tickers) or thin .NZ names frequently need this.
        individual_success = 0
        if still_missing:
            print(f"[tickerV2] Batch gave good data for {batch_success}/{len(self.tickers)} symbols. "
                  f"Retrying {len(still_missing)} individually (in parallel)...")
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _fetch_one(sym: str):
                try:
                    h = yf.Ticker(sym).history(period="1d")
                    if not h.empty and "Close" in h.columns and "Open" in h.columns:
                        c = h["Close"].iloc[-1]
                        o = h["Open"].iloc[0]
                        if pd.notna(c) and pd.notna(o) and float(o) != 0:
                            return sym, round(float(c), 2), round((float(c) - float(o)) / float(o) * 100.0, 2)
                except Exception:
                    pass
                return sym, None, None

            with ThreadPoolExecutor(max_workers=8) as ex:
                futures = {ex.submit(_fetch_one, s): s for s in still_missing}
                for fut in as_completed(futures):
                    sym, price, ch = fut.result()
                    if price is not None:
                        results[sym] = (price, ch)
                        individual_success += 1

        # Assemble final list in original ticker order, with stale fallback
        new_data: list[tuple] = []
        for symbol in self.tickers:
            if symbol in results:
                price, change = results[symbol]
            elif symbol in prev_map:
                price, change = prev_map[symbol]  # stale is better than blank
            else:
                price = change = None
            new_data.append((symbol, price, change))

        still_na = [s for s in self.tickers if s not in results and s not in prev_map]
        if individual_success:
            print(f"[tickerV2] Individual retries succeeded for {individual_success} more symbols.")
        if still_na:
            print(f"[tickerV2] {len(still_na)} symbols still have no data this cycle (will show N/A or stale).")

        return new_data

    def fetch_data(self):
        """Worker thread loop. Interruptible sleep for responsive force-refresh & exit."""
        while not self.stop_event.is_set():
            data = self._perform_fetch()
            try:
                self.data_queue.put_nowait(data)
            except queue.Full:
                pass

            # Interruptible wait (0.2s granularity so force-refresh reacts fast)
            waited = 0.0
            while waited < self.fetch_interval and not self.stop_event.is_set():
                time.sleep(0.2)
                waited += 0.2
                if self.force_refresh.is_set():
                    self.force_refresh.clear()
                    break

    def _start_background_thread(self):
        t = threading.Thread(target=self.fetch_data, daemon=True, name="TickerFetch")
        t.start()

    # --------------------------- UI Update (main thread only) ---------------------------
    def _schedule_queue_drain(self):
        self._drain_queue()
        self.root.after(120, self._schedule_queue_drain)

    def _drain_queue(self):
        updated = False
        while True:
            try:
                data = self.data_queue.get_nowait()
                with self.data_lock:
                    self.ticker_data = data
                updated = True
            except queue.Empty:
                break
        if updated:
            self._render_ticker_display()

    def _render_ticker_display(self):
        """(Re)build ticker items on canvas. Only called when data actually changes."""
        self.canvas.delete("all")
        self.content_width = 0.0
        self.offset = 0.0

        if not self.ticker_data:
            self.canvas.create_text(
                self.screen_width // 2,
                self.window_height // 2,
                text="Loading market data...",
                font=FONT,
                fill=LOADING_COLOR,
                anchor="c",
            )
            return

        # Build (text, color) list once
        entries: list[tuple[str, str]] = []
        for symbol, price, change in self.ticker_data:
            if price is None or change is None:
                txt = f"{symbol}: N/A"
                fg = GRAY
            else:
                txt = f"{symbol}: ${price:.2f} ({change:+.2f}%)"
                fg = GREEN if change >= 0 else RED
            entries.append((txt, fg))

        if not entries:
            return

        # Draw TWO copies back-to-back for seamless wrap-around
        x = 0.0
        for _ in range(2):
            for txt, fg in entries:
                tid = self.canvas.create_text(
                    x,
                    self.window_height // 2,
                    text=txt,
                    font=FONT,
                    fill=fg,
                    anchor="w",
                    tags=("ticker",),
                )
                b = self.canvas.bbox(tid)
                w = float(b[2] - b[0] + 1) if b else 70.0
                x += w + SPACER_PX

                sid = self.canvas.create_text(
                    x,
                    self.window_height // 2,
                    text=SEPARATOR,
                    font=FONT,
                    fill=WHITE,
                    anchor="w",
                    tags=("ticker",),
                )
                b = self.canvas.bbox(sid)
                sw = float(b[2] - b[0] + 1) if b else 14.0
                x += sw + SPACER_PX

        self.content_width = x / 2.0

        # Shift the entire 2x block so the head starts just off the right edge
        self.canvas.move("ticker", float(self.screen_width), 0.0)
        self.offset = 0.0

    # --------------------------- Animation (cheap!) ---------------------------
    def animate(self):
        """High-frequency but very cheap: only move existing tagged items + wrap check."""
        if (
            self.paused
            or self.content_width < 10.0
            or not self.ticker_data
            or not self.canvas.find_withtag("ticker")
        ):
            self.root.after(FRAME_INTERVAL_MS * 3, self.animate)
            return

        self.canvas.move("ticker", -self.scroll_speed, 0.0)
        self.offset -= self.scroll_speed

        if self.offset <= -self.content_width:
            self.canvas.move("ticker", self.content_width, 0.0)
            self.offset += self.content_width

        self.root.after(FRAME_INTERVAL_MS, self.animate)

    # --------------------------- User Actions ---------------------------
    def show_context_menu(self, event):
        try:
            self.menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"[tickerV2] Menu error: {e}")

    def add_ticker(self):
        symbol = simpledialog.askstring(
            "Add Ticker", "Enter ticker symbol (e.g. AAPL, BHP.AX, ^GSPC):", parent=self.root
        )
        if not symbol:
            return
        symbol = symbol.strip().upper()
        if not symbol:
            return
        if symbol in self.tickers:
            messagebox.showwarning("Ticker", f"{symbol} already tracked.", parent=self.root)
            return
        self.tickers.append(symbol)
        self.save_config()
        self.force_refresh.set()
        messagebox.showinfo("Ticker", f"Added {symbol}. Refreshing data...", parent=self.root)

    def remove_ticker(self):
        symbol = simpledialog.askstring(
            "Remove Ticker", "Enter exact ticker symbol to remove:", parent=self.root
        )
        if not symbol:
            return
        symbol = symbol.strip().upper()
        if symbol not in self.tickers:
            messagebox.showwarning("Ticker", f"{symbol} not found.", parent=self.root)
            return
        self.tickers.remove(symbol)
        self.save_config()
        self.force_refresh.set()
        messagebox.showinfo("Ticker", f"Removed {symbol}.", parent=self.root)

    def _force_refresh(self):
        self.force_refresh.set()
        # visual hint - will be overwritten quickly by next render
        self.canvas.delete("all")
        self.canvas.create_text(
            self.screen_width // 2,
            self.window_height // 2,
            text="Refreshing...",
            font=FONT,
            fill=LOADING_COLOR,
            anchor="c",
        )

    def _toggle_pause(self):
        self.paused = not self.paused
        status = "PAUSED" if self.paused else "RESUMED"
        # transient overlay
        self.canvas.delete("pause_hint")
        hint = self.canvas.create_text(
            12,
            self.window_height // 2,
            text=f"[{status}]",
            font=FONT,
            fill="#ffaa00",
            anchor="w",
            tags=("pause_hint", "ticker"),
        )
        # auto-remove after 1.2s
        self.root.after(1200, lambda: self.canvas.delete(hint) if self.canvas.winfo_exists() else None)

    def _show_ticker_list(self):
        if not self.tickers:
            msg = "No tickers configured."
        else:
            lines = "\n".join(f"  • {t}" for t in self.tickers)
            msg = f"Tracking {len(self.tickers)} symbols:\n{lines}"
        messagebox.showinfo("Current Tickers", msg, parent=self.root)

    def exit_app(self):
        self.stop_event.set()
        self.force_refresh.set()
        try:
            self.root.destroy()
        except Exception:
            pass


# --------------------------- Entry Point ---------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Stock Market Ticker Tape V2 - improved scrolling display"
    )
    parser.add_argument(
        "-c", "--config", default=DEFAULT_YAML, help="Path to tickers YAML config file"
    )
    parser.add_argument(
        "--dock", choices=["top", "bottom"], help="Force dock position (overrides saved config)"
    )
    parser.add_argument(
        "--speed", type=float, default=SCROLL_SPEED, help=f"Scroll speed px/frame (default {SCROLL_SPEED})"
    )
    parser.add_argument(
        "--interval", type=int, default=FETCH_INTERVAL_SEC, help=f"Fetch interval seconds (default {FETCH_INTERVAL_SEC})"
    )
    parser.add_argument(
        "--height", type=int, default=WINDOW_HEIGHT, help=f"Window height px (default {WINDOW_HEIGHT})"
    )
    args = parser.parse_args()

    root = tk.Tk()
    TickerTape(
        root,
        yaml_file=args.config,
        dock_position=args.dock,
        scroll_speed=args.speed,
        fetch_interval=args.interval,
        window_height=args.height,
    )
    root.mainloop()


if __name__ == "__main__":
    main()
