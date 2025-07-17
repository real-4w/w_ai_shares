import tkinter as tk
from tkinter import simpledialog, messagebox
import yfinance as yf
import yaml
import os
import threading
import time
import win32api
import win32con
import win32gui

class TickerTape:
    def __init__(self, root):
        self.root = root
        self.root.title("Stock Market Ticker")
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.window_height = 30  # Single-line height
        # Estimate taskbar height (Windows 11 default is ~48 pixels)
        self.taskbar_height = self.get_taskbar_height() or 48
        # Initialize docking position (default to top)
        self.dock_position = 'top'
        self.yaml_file = 'tickers.yaml'
        self.load_config()
        self.update_geometry()
        self.root.attributes('-topmost', True)  # Keep on top
        self.root.overrideredirect(True)  # Remove window borders
        self.root.configure(bg='black')

        # Make window click-through
        self.make_click_through()

        # Ticker symbols (default indices)
        self.tickers = [
            '^GSPC',  # S&P 500 (USA)
            '^AXJO',  # ASX 200 (Australia)
            '^NZ50'   # NZX 50 (NZ)
        ]
        self.load_config()  # Load tickers after setting default

        # Label for scrolling text
        self.label = tk.Label(
            root,
            text="",
            font=("Arial", 12),
            fg="white",
            bg="black",
            anchor="w",
            justify="left"
        )
        self.label.pack(fill='both', expand=True)

        # Bind right-click for context menu on both label and root
        self.label.bind("<Button-3>", self.show_context_menu)
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
        self.ticker_data = [(symbol, None, None) for symbol in self.tickers]
        self.text = "  |  ".join(f"{symbol}: Initialising..." for symbol in self.tickers)
        self.x_pos = self.screen_width
        self.running = True

        # Initialize display
        self.update_label_text()
        self.root.update()  # Force immediate render

        # Start data fetching and animation
        self.fetch_thread = threading.Thread(target=self.fetch_data, daemon=True)
        self.fetch_thread.start()
        self.root.after(20, self.animate)

    def get_taskbar_height(self):
        """Get the height of the Windows taskbar."""
        try:
            monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0, 0)))
            work_area = monitor_info['Work']
            full_area = monitor_info['Monitor']
            return full_area[3] - work_area[3]
        except Exception as e:
            print(f"Error getting taskbar height: {e}")
            return None

    def make_click_through(self):
        """Make the window click-through to allow taskbar interaction."""
        try:
            hwnd = self.root.winfo_id()
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        except Exception as e:
            print(f"Error setting click-through: {e}")

    def load_config(self):
        """Load tickers and dock position from YAML file."""
        try:
            if os.path.exists(self.yaml_file):
                with open(self.yaml_file, 'r') as file:
                    data = yaml.safe_load(file)
                    if data:
                        if 'tickers' in data:
                            self.tickers = data['tickers']
                            self.ticker_data = [(symbol, None, None) for symbol in self.tickers]
                            self.text = "  |  ".join(f"{symbol}: Initialising..." for symbol in self.tickers)
                        if 'dock_position' in data:
                            self.dock_position = data['dock_position']
                            self.update_geometry()
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save tickers and dock position to YAML file."""
        try:
            with open(self.yaml_file, 'w') as file:
                yaml.dump({
                    'tickers': self.tickers,
                    'dock_position': self.dock_position
                }, file)
        except Exception as e:
            print(f"Error saving config: {e}")

    def update_geometry(self):
        """Update window geometry based on dock position."""
        try:
            if self.dock_position == 'top':
                y_pos = 0
            else:
                y_pos = self.screen_height - self.window_height - self.taskbar_height
            self.root.geometry(f"{self.screen_width}x{self.window_height}+0+{y_pos}")
            self.root.update_idletasks()
        except Exception as e:
            print(f"Error updating geometry: {e}")

    def set_dock_position(self, position):
        """Set docking position and update geometry."""
        try:
            if position in ['top', 'bottom'] and position != self.dock_position:
                self.dock_position = position
                self.update_geometry()
                self.save_config()
                messagebox.showinfo("Success", f"Ticker tape docked to {position} of screen.")
        except Exception as e:
            print(f"Error setting dock position: {e}")

    def fetch_data(self):
        """Fetch stock data periodically."""
        try:
            # Initial fetch
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
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    ticker_data.append((symbol, None, None))
            self.ticker_data = ticker_data
            self.root.after(0, self.update_label_text)

            # Periodic updates
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
                    except Exception as e:
                        print(f"Error fetching data for {symbol}: {e}")
                        ticker_data.append((symbol, None, None))
                self.ticker_data = ticker_data
                self.root.after(0, self.update_label_text)
                time.sleep(60)
        except Exception as e:
            print(f"Error in fetch_data: {e}")

    def update_label_text(self):
        """Update the label text with current ticker data."""
        try:
            text_parts = []
            fg = "white"
            for symbol, price, change in self.ticker_data:
                if price is None or change is None:
                    text = f"{symbol}: Initialising..." if all(p is None and c is None for s, p, c in self.ticker_data) else f"{symbol}: No data"
                else:
                    text = f"{symbol}: ${price:.2f} ({change:+.2f}%)"
                    fg = "green" if change >= 0 else "red"
                text_parts.append(text)
            self.text = "  |  ".join(text_parts)
            self.label.config(text=self.text, fg=fg)
            self.label.place(x=self.x_pos, y=0)
            self.root.update()
        except Exception as e:
            print(f"Error updating label text: {e}")

    def animate(self):
        """Animate scrolling label."""
        try:
            self.x_pos -= 2  # Scroll speed
            text_width = self.label.winfo_reqwidth()
            if self.x_pos < -text_width:
                self.x_pos = self.screen_width
            self.label.place(x=self.x_pos, y=0)
            self.root.update()
            self.root.after(20, self.animate)
        except Exception as e:
            print(f"Error in animation: {e}")
            self.root.after(100, self.animate)

    def show_context_menu(self, event):
        """Show right-click context menu."""
        try:
            self.menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Error displaying context menu: {e}")

    def add_ticker(self):
        """Add a new ticker symbol."""
        try:
            symbol = simpledialog.askstring("Add Ticker", "Enter ticker symbol (e.g., AAPL):", parent=self.root)
            if symbol:
                symbol = symbol.strip().upper()
                if symbol not in self.tickers:
                    self.tickers.append(symbol)
                    self.ticker_data.append((symbol, None, None))
                    self.update_label_text()
                    self.save_config()
                    messagebox.showinfo("Success", f"Added {symbol} to ticker tape.")
                else:
                    messagebox.showwarning("Warning", f"{symbol} is already in the ticker tape.")
        except Exception as e:
            print(f"Error adding ticker: {e}")

    def remove_ticker(self):
        """Remove a ticker symbol."""
        try:
            symbol = simpledialog.askstring("Remove Ticker", "Enter ticker symbol to remove:", parent=self.root)
            if symbol:
                symbol = symbol.strip().upper()
                if symbol in self.tickers:
                    self.tickers.remove(symbol)
                    self.ticker_data = [(s, p, c) for s, p, c in self.ticker_data if s != symbol]
                    self.update_label_text()
                    self.save_config()
                    messagebox.showinfo("Success", f"Removed {symbol} from ticker tape.")
                else:
                    messagebox.showwarning("Warning", f"{symbol} not found in ticker tape.")
        except Exception as e:
            print(f"Error removing ticker: {e}")

    def exit_app(self):
        """Exit the application."""
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = TickerTape(root)
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {e}")