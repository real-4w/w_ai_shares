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
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.window_height = 30  # Single-line height
        # Initialize docking position (default to top)
        self.dock_position = 'top'
        self.yaml_file = 'tickers.yaml'
        self.load_config()
        self.update_geometry()
        self.root.attributes('-topmost', True)  # Keep on top
        self.root.overrideredirect(True)  # Remove window borders
        self.root.configure(bg='black')

        # Ticker symbols (default indices)
        self.tickers = [
            '^GSPC',  # S&P 500 (USA)
            '^AXJO',  # ASX 200 (Australia)
            '^NZ50'   # NZX 50 (NZ)
        ]
        self.load_config()  # Load tickers after setting default

        # Canvas for scrolling labels
        self.canvas = tk.Canvas(
            root,
            bg='black',
            highlightthickness=0,
            height=self.window_height
        )
        self.canvas.pack(fill='both', expand=True)

        # Bind right-click for context menu on both canvas and root
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<Button-3>", self.show_context_menu)

        # Context menu
        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Add Ticker", command=self.add_ticker)
        self.menu.add_command(label="Remove Ticker", command=self.remove_ticker)
        self.menu.add_command(label="Dock to Top", command=lambda: self.set_dock_position('top'))
        self.menu.add_command(label="Dock to Bottom", command=lambda: self.set_dock_position('bottom'))
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.exit_app)

        # Animation variables
        self.ticker_data = []
        self.labels = []
        self.total_width = 0
        self.x_pos = self.screen_width  # Start off-screen
        self.running = True

        # Start data fetching and animation
        self.fetch_thread = threading.Thread(target=self.fetch_data, daemon=True)
        self.fetch_thread.start()
        self.animate()

    def load_config(self):
        """Load tickers and dock position from YAML file."""
        if os.path.exists(self.yaml_file):
            with open(self.yaml_file, 'r') as file:
                data = yaml.safe_load(file)
                if data:
                    if 'tickers' in data:
                        self.tickers = data['tickers']
                    if 'dock_position' in data:
                        self.dock_position = data['dock_position']
                        self.update_geometry()

    def save_config(self):
        """Save tickers and dock position to YAML file."""
        with open(self.yaml_file, 'w') as file:
            yaml.dump({
                'tickers': self.tickers,
                'dock_position': self.dock_position
            }, file)

    def update_geometry(self):
        """Update window geometry based on dock position."""
        y_pos = 0 if self.dock_position == 'top' else self.screen_height - self.window_height
        self.root.geometry(f"{self.screen_width}x{self.window_height}+0+{y_pos}")
        self.root.update_idletasks()  # Ensure geometry update is applied

    def set_dock_position(self, position):
        """Set docking position and update geometry."""
        if position in ['top', 'bottom'] and position != self.dock_position:
            self.dock_position = position
            self.update_geometry()
            self.save_config()
            messagebox.showinfo("Success", f"Ticker tape docked to {position} of screen.")

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
                self.window_height // 2,  # Center vertically
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
                self.window_height // 2,
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
            self.x_pos = self.screen_width  # Reset to screen width

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
                self.window_height // 2,
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
                self.window_height // 2,
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
        try:
            self.menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Error displaying context menu: {e}")  # Debug output

    def add_ticker(self):
        """Add a new ticker symbol."""
        symbol = simpledialog.askstring("Add Ticker", "Enter ticker symbol (e.g., AAPL):", parent=self.root)
        if symbol:
            symbol = symbol.strip().upper()
            if symbol not in self.tickers:
                self.tickers.append(symbol)
                self.save_config()
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
                self.save_config()
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