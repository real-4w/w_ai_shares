import tkinter as tk
from tkinter import simpledialog, messagebox
import yfinance as yf
import yaml
import os
from datetime import datetime
import threading
import time

class TickerTape:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Market Ticker")
        # Set width to full screen width
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"{screen_width}x50+0+0")  # Span full screen width
        self.root.attributes('-topmost', True)  # Keep on top
        self.root.overrideredirect(True)  # Remove window borders
        self.root.configure(bg='black')

        # Ticker symbols (default indices)
        self.tickers = [
            '^GSPC',  # S&P 500 (USA)
            '^AXJO',  # ASX 200 (Australia)
            '^NZ50'   # NZX 50 (NZ)
        ]
        self.yaml_file = 'tickers.yaml'
        self.load_tickers()

        # Scrolling text
        self.label = tk.Label(
            root,
            text="",
            font=("Arial", 14),
            fg="green",
            bg="black",
            anchor="w",
            padx=10
        )
        self.label.pack(fill="both", expand=True)

        # Bind right-click for context menu
        self.label.bind("<Button-3>", self.show_context_menu)

        # Context menu
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Add Ticker", command=self.add_ticker)
        self.menu.add_command(label="Remove Ticker", command=self.remove_ticker)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)

        # Animation variables
        self.text = ""
        self.text_width = 0
        self.x_pos = screen_width  # Start off-screen at screen width
        self.running = True

        # Start data fetching and animation
        self.fetch_thread = threading.Thread(target=self.fetch_data, daemon=True)
        self.fetch_thread.start()
        self.animate()

    def load_tickers(self):
        """Load tickers from YAML file."""
        if os.path.exists(self.yaml_file):
            with open(self.yaml_file, 'r') as file:
                data = yaml.safe_load(file)
                if data and 'tickers' in data:
                    self.tickers = data['tickers']

    def save_tickers(self):
        """Save tickers to YAML file."""
        with open(self.yaml_file, 'w') as file:
            yaml.dump({'tickers': self.tickers}, file)

    def fetch_data(self):
        """Fetch stock data periodically."""
        while self.running:
            ticker_data = []
            for symbol in self.tickers:
                try:
                    stock = yf.Ticker(symbol)
                    data = stock.history(period="1d")
                    if not data.empty:
                        price = data['Close'].iloc[-1]
                        change = ((price - data['Open'].iloc[0]) / data['Open'].iloc[0]) * 100
                        ticker_data.append(f"{symbol}: ${price:.2f} ({change:+.2f}%)")
                    else:
                        ticker_data.append(f"{symbol}: No data")
                except Exception:
                    ticker_data.append(f"{symbol}: Error")
            self.text = "    |    ".join(ticker_data) + "    |    "
            time.sleep(60)  # Update every minute

    def animate(self):
        """Animate scrolling text."""
        if not self.text:
            self.root.after(100, self.animate)
            return

        # Calculate text width
        self.label.config(text=self.text)
        self.text_width = self.label.winfo_reqwidth()
        self.x_pos -= 2  # Scroll speed

        if self.x_pos < -self.text_width:
            self.x_pos = self.root.winfo_screenwidth()  # Reset to screen width

        # Update label position
        self.label.place(x=self.x_pos, y=0, width=self.text_width)
        self.root.after(20, self.animate)  # Update every 20ms

    def show_context_menu(self, event):
        """Show right-click context menu."""
        self.menu.post(event.x_root, event.y_root)

    def add_ticker(self):
        """Add a new ticker symbol."""
        symbol = simpledialog.askstring("Add Ticker", "Enter ticker symbol (e.g., AAPL):", parent=self.root)
        if symbol:
            symbol = symbol.strip().upper()
            if symbol not in self.tickers:
                self.tickers.append(symbol)
                self.save_tickers()
                messagebox.showinfo("Success", f"Added {symbol} to ticker tape.")
            else:
                messagebox.showwarning("Warning", f"{symbol} is already in the ticker tape.")

    def remove_ticker(self):
        """Remove a ticker symbol."""
        symbol = simpledialog.askstring("Remove Ticker", "Enter ticker symbol to remove:", parent=self.root)
        if symbol:
            symbol = symbol.strip().upper()
            if symbol in self.tickers:
                self.tickers.remove(symbol)
                self.save_tickers()
                messagebox.showinfo("Success", f"Removed {symbol} from ticker tape.")
            else:
                messagebox.showwarning("Warning", f"{symbol} not found in ticker tape.")

    def exit_app(self):
        """Exit the application."""
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TickerTape(root)
    root.mainloop()