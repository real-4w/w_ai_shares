import tkinter as tk
from tkinter import simpledialog, messagebox
import yfinance as yf
import yaml
import os
import threading
import time

class TickerTape:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Market Ticker")
        # Set width to full screen width, height to one line
        screen_width = self.root.winfo_screenwidth()
        self.root.geometry(f"{screen_width}x30+0+0")  # Span full screen, 30px tall
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

        # Canvas for scrolling labels
        self.canvas = tk.Canvas(
            root,
            bg='black',
            highlightthickness=0,
            height=30
        )
        self.canvas.pack(fill='both', expand=True)

        # Bind right-click for context menu
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # Context menu
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Add Ticker", command=self.add_ticker)
        self.menu.add_command(label="Remove Ticker", command=self.remove_ticker)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)

        # Animation variables
        self.ticker_data = []
        self.labels = []
        self.total_width = 0
        self.x_pos = screen_width  # Start off-screen
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
                        ticker_data.append((symbol, price, change))
                    else:
                        ticker_data.append((symbol, None, None))
                except Exception:
                    ticker_data.append((symbol, None, None))
            self.ticker_data = ticker_data
            self.update_labels()
            time.sleep(60)  # Update every minute

    def update_labels(self):
        """Update or create labels for ticker data."""
        # Clear existing labels
        for label in self.labels:
            self.canvas.delete(label)
        self.labels = []

        x_offset = 0
        for symbol, price, change in self.ticker_data:
            if price is None or change is None:
                text = f"{symbol}: No data"
                fg = "white"
            else:
                text = f"{symbol}: ${price:.2f} ({change:+.2f}%)"
                fg = "green" if change >= 0 else "red"

            # Create label on canvas
            label_id = self.canvas.create_text(
                x_offset,
                15,  # Center vertically
                text=text,
                font=("Arial", 12),
                fill=fg,
                anchor="w"
            )
            self.labels.append(label_id)

            # Calculate width
            bbox = self.canvas.bbox(label_id)
            width = bbox[2] - bbox[0]
            x_offset += width + 40  # Space between tickers

            # Add separator
            sep_id = self.canvas.create_text(
                x_offset,
                15,
                text="|",
                font=("Arial", 12),
                fill="white",
                anchor="w"
            )
            self.labels.append(sep_id)
            bbox = self.canvas.bbox(sep_id)
            x_offset += (bbox[2] - bbox[0]) + 40

        self.total_width = x_offset

    def animate(self):
        """Animate scrolling labels."""
        if not self.ticker_data:
            self.root.after(100, self.animate)
            return

        self.x_pos -= 2  # Scroll speed
        if self.x_pos < -self.total_width:
            self.x_pos = self.root.winfo_screenwidth()  # Reset to screen width

        # Move all labels
        self.canvas.delete("all")
        self.labels = []
        x_offset = self.x_pos
        for symbol, price, change in self.ticker_data:
            if price is None or change is None:
                text = f"{symbol}: No data"
                fg = "white"
            else:
                text = f"{symbol}: ${price:.2f} ({change:+.2f}%)"
                fg = "green" if change >= 0 else "red"

            label_id = self.canvas.create_text(
                x_offset,
                15,
                text=text,
                font=("Arial", 12),
                fill=fg,
                anchor="w"
            )
            self.labels.append(label_id)
            bbox = self.canvas.bbox(label_id)
            x_offset += (bbox[2] - bbox[0]) + 40

            sep_id = self.canvas.create_text(
                x_offset,
                15,
                text="|",
                font=("Arial", 12),
                fill="white",
                anchor="w"
            )
            self.labels.append(sep_id)
            bbox = self.canvas.bbox(sep_id)
            x_offset += (bbox[2] - bbox[0]) + 40

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