import yfinance as yf
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import time
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import json
import os
import logging

class StockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Enhanced Stock Investment App")
        self.root.geometry("700x600")
        self.root.configure(bg="#f0f0f0")

        # Setup logging
        logging.basicConfig(filename='stock_app.log', level=logging.INFO,
                           format='%(asctime)s - %(levelname)s - %(message)s')

        # Load or initialize ticker tape stocks
        self.ticker_stocks = self.load_ticker_stocks()
        self.ticker_prices = {}
        self.running = True
        self.cache = {}  # Cache for stock data
        self.cache_timeout = 300  # Cache for 5 minutes

        # Configure main frame
        self.frame = tk.Frame(self.root, padx=10, pady=10, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True)

        # Ticker tape frame
        self.ticker_frame = tk.Frame(self.frame, bg="black")
        self.ticker_frame.pack(fill="x", pady=5)
        self.ticker_label = tk.Label(self.ticker_frame, text="Loading ticker tape...", font=("Courier", 12), bg="black", fg="yellow", anchor="w")
        self.ticker_label.pack(fill="x")

        # Ticker management frame
        self.ticker_mgmt_frame = tk.Frame(self.frame, bg="#f0f0f0")
        self.ticker_mgmt_frame.pack(fill="x", pady=5)
        tk.Label(self.ticker_mgmt_frame, text="Add/Remove Ticker:", bg="#f0f0f0").pack(side="left")
        self.ticker_mgmt_entry = tk.Entry(self.ticker_mgmt_frame, width=15)
        self.ticker_mgmt_entry.pack(side="left", padx=5)
        tk.Button(self.ticker_mgmt_frame, text="Add", command=self.add_ticker).pack(side="left", padx=5)
        tk.Button(self.ticker_mgmt_frame, text="Remove", command=self.remove_ticker).pack(side="left", padx=5)

        # Input frame
        self.input_frame = tk.Frame(self.frame, bg="#f0f0f0")
        self.input_frame.pack(fill="x", pady=5)
        tk.Label(self.input_frame, text="Enter Stock Ticker (e.g., AAPL, BHP.AX, AIA.NZ):", bg="#f0f0f0", font=("Arial", 10)).pack(anchor="w")
        self.ticker_entry = tk.Entry(self.input_frame, width=20, font=("Arial", 10))
        self.ticker_entry.pack(anchor="w", pady=5)

        # Button frame
        self.button_frame = tk.Frame(self.frame, bg="#f0f0f0")
        self.button_frame.pack(fill="x", pady=5)
        tk.Button(self.button_frame, text="Get Stock Info", command=self.get_stock_info, bg="#4CAF50", fg="white").pack(side="left", padx=5)
        tk.Button(self.button_frame, text="Show Chart", command=self.show_chart, bg="#2196F3", fg="white").pack(side="left", padx=5)
        tk.Button(self.button_frame, text="Export to CSV", command=self.export_to_csv, bg="#FF9800", fg="white").pack(side="left", padx=5)
        tk.Button(self.button_frame, text="Clear Output", command=self.clear_output, bg="#F44336", fg="white").pack(side="left", padx=5)

        # Output area
        self.output_text = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, height=20, width=80, font=("Arial", 10))
        self.output_text.pack(fill="both", expand=True, pady=10)

        # Start ticker tape update
        self.update_ticker_tape()

        # Display daily recommendations on startup
        self.display_daily_recommendations()

    def load_ticker_stocks(self):
        """Load ticker stocks from a JSON file or use defaults."""
        default_tickers = ['AAPL', 'MSFT', 'BHP.AX', 'CBA.AX', 'AIA.NZ', 'FPH.NZ']
        if os.path.exists('ticker_stocks.json'):
            try:
                with open('ticker_stocks.json', 'r') as f:
                    tickers = json.load(f)
                    logging.info(f"Loaded ticker stocks: {tickers}")
                    return tickers
            except Exception as e:
                logging.error(f"Failed to load ticker stocks: {e}")
        return default_tickers

    def save_ticker_stocks(self):
        """Save ticker stocks to a JSON file."""
        try:
            with open('ticker_stocks.json', 'w') as f:
                json.dump(self.ticker_stocks, f)
            logging.info(f"Saved ticker stocks: {self.ticker_stocks}")
        except Exception as e:
            logging.error(f"Failed to save ticker stocks: {e}")

    def add_ticker(self):
        """Add a ticker to the ticker tape."""
        ticker = self.ticker_mgmt_entry.get().strip().upper()
        if not ticker:
            messagebox.showerror("Error", "Ticker cannot be empty.")
            return

        # Validate ticker by attempting to fetch data
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if 'currentPrice' not in info or info['currentPrice'] is None:
                messagebox.showerror("Error", f"Invalid ticker or no data available for {ticker}.")
                return
        except Exception as e:
            logging.error(f"Validation error for {ticker}: {e}")
            messagebox.showerror("Error", f"Failed to validate {ticker}: {str(e)}")
            return

        # Check for duplicates
        if ticker not in self.ticker_stocks:
            self.ticker_stocks.append(ticker)
            self.save_ticker_stocks()
            self.ticker_mgmt_entry.delete(0, tk.END)
            messagebox.showinfo("Success", f"{ticker} added to ticker tape.")
        else:
            logging.info(f"Attempted to add duplicate ticker: {ticker}. Current tickers: {self.ticker_stocks}")
            messagebox.showwarning("Warning", f"{ticker} is already in the ticker tape.")

    def remove_ticker(self):
        """Remove a ticker from the ticker tape."""
        ticker = self.ticker_mgmt_entry.get().strip().upper()
        if not ticker:
            messagebox.showerror("Error", "Ticker cannot be empty.")
            return

        if ticker in self.ticker_stocks:
            self.ticker_stocks.remove(ticker)
            self.save_ticker_stocks()
            self.ticker_mgmt_entry.delete(0, tk.END)
            messagebox.showinfo("Success", f"{ticker} removed from ticker tape.")
        else:
            logging.info(f"Attempted to remove non-existent ticker: {ticker}. Current tickers: {self.ticker_stocks}")
            messagebox.showwarning("Warning", f"{ticker} not found in ticker tape.")

    def update_ticker_tape(self):
        """Update the ticker tape with stock prices and percentage changes."""
        if not self.running:
            return

        ticker_text = ""
        for ticker in self.ticker_stocks:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                price = info.get('currentPrice', 'N/A')
                prev_close = info.get('previousClose', None)
                change_percent = ((price - prev_close) / prev_close * 100) if price != 'N/A' and prev_close else 'N/A'
                self.ticker_prices[ticker] = (price, change_percent)
                ticker_text += f"{ticker}: ${price:.2f} ({change_percent:+.2f}%)  |  " if change_percent != 'N/A' else f"{ticker}: ${price:.2f}  |  "
            except Exception as e:
                self.ticker_prices[ticker] = ('N/A', 'N/A')
                ticker_text += f"{ticker}: N/A  |  "
                logging.error(f"Ticker tape error for {ticker}: {e}")

        # Update ticker label
        if not ticker_text:
            ticker_text = "No data available for ticker tape stocks. Please check logs or try adding new tickers."
        self.ticker_label.config(text=ticker_text)

        # Implement scrolling using root.after
        def scroll_text(pos=0):
            if not self.running:
                return
            self.ticker_label.config(text=ticker_text[pos:] + ticker_text[:pos])
            pos = (pos + 1) % (len(ticker_text) + 50) if ticker_text else 0
            self.root.after(100, scroll_text, pos)

        scroll_text()
        self.root.after(120000, self.update_ticker_tape)  # Update every 120 seconds

    def fetch_stock_data(self, ticker):
        """Fetch stock data using yfinance with caching."""
        current_time = time.time()
        if ticker in self.cache and current_time - self.cache[ticker]['timestamp'] < self.cache_timeout:
            return self.cache[ticker]['data']

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            recommendations = stock.recommendations_summary
            prev_close = info.get('previousClose', None)
            current_price = info.get('currentPrice', 'N/A')
            change_percent = ((current_price - prev_close) / prev_close * 100) if current_price != 'N/A' and prev_close else 'N/A'

            analyst_ratings = None
            recommendation_mean = info.get('recommendationMean', 'N/A')
            if not recommendations.empty:
                expected_columns = ['Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell']
                available_columns = [col for col in expected_columns if col in recommendations.columns]
                if available_columns:
                    analyst_ratings = recommendations[available_columns].tail(1)
                else:
                    logging.info(f"No expected rating columns for {ticker}. Columns: {recommendations.columns.tolist()}")
            else:
                logging.info(f"Empty recommendations_summary for {ticker}")

            stock_data = {
                'Company Name': info.get('longName', 'N/A'),
                'Ticker': ticker.upper(),
                'Current Price': current_price,
                'Daily Change (%)': f"{change_percent:+.2f}" if change_percent != 'N/A' else 'N/A',
                'Market Cap (Billion USD)': round(info.get('marketCap', 0) / 1e9, 2) if info.get('marketCap') else 'N/A',
                'P/E Ratio': info.get('trailingPE', 'N/A'),
                'Forward P/E': info.get('forwardPE', 'N/A'),
                'Dividend Yield (%)': round(info.get('dividendYield', 0) * 100, 2) if info.get('dividendYield') else 'N/A',
                '52-Week High': info.get('fiftyTwoWeekHigh', 'N/A'),
                '52-Week Low': info.get('fiftyTwoWeekLow', 'N/A'),
                'Average Analyst Price Target': info.get('targetMeanPrice', 'N/A'),
                'Recommendation Mean': recommendation_mean,
                'Date Retrieved': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Analyst Ratings': analyst_ratings
            }
            self.cache[ticker] = {'data': stock_data, 'timestamp': current_time}
            return stock_data
        except Exception as e:
            logging.error(f"Fetch stock data error for {ticker}: {e}")
            return {'Error': f"Error retrieving data for {ticker}: {str(e)}"}

    def display_stock_data(self, stock_data, ticker):
        """Display stock data in the output text area."""
        self.output_text.insert(tk.END, f"\nInvestment Information for {ticker}\n")
        self.output_text.insert(tk.END, "-" * 50 + "\n")

        if 'Error' in stock_data:
            self.output_text.insert(tk.END, f"{stock_data['Error']}\n\n")
            return

        for key, value in stock_data.items():
            if key not in ['Analyst Ratings']:
                self.output_text.insert(tk.END, f"{key}: {value}\n")

        self.output_text.insert(tk.END, "\nAnalyst Ratings Summary (Last 30 Days)\n")
        self.output_text.insert(tk.END, "-" * 50 + "\n")
        if stock_data['Analyst Ratings'] is not None:
            self.output_text.insert(tk.END, stock_data['Analyst Ratings'].to_string(index=False) + "\n")
        else:
            self.output_text.insert(tk.END, "No recent analyst ratings available.\n")
        self.output_text.insert(tk.END, "\n")
        self.output_text.see(tk.END)

    def get_stock_info(self):
        """Retrieve and display stock info for the user-entered ticker."""
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showerror("Error", "Ticker symbol cannot be empty.")
            return

        self.output_text.insert(tk.END, f"Fetching data for {ticker}...\n")
        self.output_text.see(tk.END)
        self.root.update()

        stock_data = self.fetch_stock_data(ticker)
        self.display_stock_data(stock_data, ticker)

    def show_chart(self):
        """Show a 30-day price history chart for the entered ticker."""
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showerror("Error", "Please enter a ticker to show the chart.")
            return

        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1mo")
            if hist.empty:
                messagebox.showerror("Error", f"No historical data available for {ticker}.")
                return

            fig, ax = plt.subplots(figsize=(6, 4))
            ax.plot(hist.index, hist['Close'], label=f"{ticker} Closing Price")
            ax.set_title(f"{ticker} 30-Day Price History")
            ax.set_xlabel("Date")
            ax.set_ylabel("Price (USD)")
            ax.legend()
            ax.grid(True)
            plt.xticks(rotation=45)

            chart_window = tk.Toplevel(self.root)
            chart_window.title(f"{ticker} Price Chart")
            canvas = FigureCanvasTkAgg(fig, master=chart_window)
            canvas.draw()
            canvas.get_tk_widget().pack()
        except Exception as e:
            logging.error(f"Chart error for {ticker}: {e}")
            messagebox.showerror("Error", f"Failed to generate chart for {ticker}: {str(e)}")

    def export_to_csv(self):
        """Export displayed stock data to a CSV file."""
        try:
            output_content = self.output_text.get(1.0, tk.END).strip()
            if not output_content:
                messagebox.showwarning("Warning", "No data to export.")
                return

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"stock_data_{timestamp}.csv"
            lines = output_content.split('\n')
            data = []
            current_stock = {}
            current_ticker = ""

            for line in lines:
                if "Investment Information for" in line:
                    if current_stock:
                        data.append(current_stock)
                    current_ticker = line.split()[-1]
                    current_stock = {'Ticker': current_ticker}
                elif ":" in line and not "Analyst Ratings" in line and not "-" in line:
                    key, value = line.split(":", 1)
                    current_stock[key.strip()] = value.strip()
                elif "Strong Buy  Buy  Hold  Sell  Strong Sell" in line:
                    next_line = lines[lines.index(line) + 1]
                    current_stock['Analyst Ratings'] = next_line.strip()
            if current_stock:
                data.append(current_stock)

            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            messagebox.showinfo("Success", f"Data exported to {filename}")
        except Exception as e:
            logging.error(f"Export error: {e}")
            messagebox.showerror("Error", f"Failed to export data: {str(e)}")

    def clear_output(self):
        """Clear the output text area."""
        self.output_text.delete(1.0, tk.END)

    def display_daily_recommendations(self):
        """Display three daily stock recommendations based on analyst ratings."""
        candidate_tickers = ['AAPL', 'MSFT', 'GOOGL', 'BHP.AX', 'CBA.AX', 'AIA.NZ', 'FPH.NZ', 'TSLA', 'WBC.AX', 'SPK.NZ']
        recommendations = []
        for ticker in candidate_tickers:
            stock_data = self.fetch_stock_data(ticker)
            if 'Error' not in stock_data:
                recommendation_mean = stock_data['Recommendation Mean']
                score = -recommendation_mean if recommendation_mean != 'N/A' else 0
                recommendations.append((ticker, score))

        recommendations.sort(key=lambda x: x[1])
        top_tickers = [ticker for ticker, _ in recommendations[:3]]

        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "Daily Stock Recommendations (Based on Analyst Ratings)\n")
        self.output_text.insert(tk.END, "=" * 50 + "\n\n")

        for ticker in top_tickers:
            stock_data = self.fetch_stock_data(ticker)
            self.display_stock_data(stock_data, ticker)

    def stop(self):
        """Stop the ticker tape thread when closing the app."""
        self.running = False

def main():
    root = tk.Tk()
    app = StockApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: [app.stop(), root.destroy()])
    root.mainloop()

if __name__ == "__main__":
    main()