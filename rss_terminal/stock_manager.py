"""
Stock Manager module for RSS Terminal.
Handles fetching stock data from Yahoo Finance and managing updates.
"""
import time
import threading
import yfinance as yf
from datetime import datetime, timedelta


class StockManager:
    """Manages stock data fetching and caching"""
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.stocks = {}  # Cache for stock data
        self.last_update_time = 0
        self.fetch_thread = None
        self.stop_fetching_flag = False
        self.fetch_callback = None
        self.current_symbol_index = 0
        
    def start_fetching(self, callback):
        """Start background stock data fetching"""
        self.fetch_callback = callback
        self.stop_fetching_flag = False
        
        # Start the background thread
        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()
        
    def stop_fetching(self):
        """Stop the background fetching thread"""
        self.stop_fetching_flag = True
        if self.fetch_thread and self.fetch_thread.is_alive():
            self.fetch_thread.join(timeout=1)
    
    def _fetch_loop(self):
        """Background loop for fetching stock data"""
        while not self.stop_fetching_flag:
            try:
                # Check if it's time to update
                current_time = time.time()
                if current_time - self.last_update_time >= self.config.stock_update_interval:
                    self.fetch_stock_data()
                    self.last_update_time = current_time
                
                # Sleep for 10 seconds before checking again
                time.sleep(10)
                
            except Exception as e:
                print(f"Stock fetch error: {e}")
                time.sleep(30)  # Wait longer on error
    
    def fetch_stock_data(self):
        """Fetch stock data for configured symbols"""
        if not self.config.stock_symbols:
            return
        
        try:
            # Fetch data for all symbols at once with timeout
            symbols_str = " ".join(self.config.stock_symbols)
            tickers = yf.Tickers(symbols_str)
            
            print(f"[DEBUG] Fetching stock data for: {symbols_str}")
            
            updated_stocks = {}
            
            for symbol in self.config.stock_symbols:
                try:
                    print(f"[DEBUG] Processing {symbol}...")
                    ticker = tickers.tickers[symbol]
                    info = ticker.info
                    hist = ticker.history(period="2d", interval="1d")
                    
                    if not hist.empty and 'regularMarketPrice' in info:
                        current_price = info.get('regularMarketPrice', 0)
                        prev_close = info.get('previousClose', current_price)
                        
                        # Calculate change
                        price_change = current_price - prev_close
                        percent_change = (price_change / prev_close * 100) if prev_close > 0 else 0
                        
                        # Market status
                        market_state = info.get('marketState', 'CLOSED')
                        
                        # After hours data if available
                        after_hours_price = info.get('postMarketPrice')
                        after_hours_change = info.get('postMarketChange')
                        
                        updated_stocks[symbol] = {
                            'symbol': symbol,
                            'current_price': current_price,
                            'previous_close': prev_close,
                            'price_change': price_change,
                            'percent_change': percent_change,
                            'market_state': market_state,
                            'after_hours_price': after_hours_price,
                            'after_hours_change': after_hours_change,
                            'last_updated': datetime.now(),
                            'company_name': info.get('shortName', symbol)
                        }
                        
                except Exception as e:
                    print(f"Error fetching data for {symbol}: {e}")
                    # Keep previous data if fetch fails
                    if symbol in self.stocks:
                        updated_stocks[symbol] = self.stocks[symbol]
            
            # Update the cache
            self.stocks = updated_stocks
            
            # Notify UI if callback is set
            if self.fetch_callback:
                self.fetch_callback(self.stocks)
                
        except Exception as e:
            print(f"Stock data fetch error: {e}")
            if self.fetch_callback:
                self.fetch_callback(None, error=True)
    
    def get_current_display_stock(self):
        """Get the currently selected stock for display cycling"""
        if not self.config.stock_symbols or not self.stocks:
            return None
            
        symbol = self.config.stock_symbols[self.current_symbol_index]
        return self.stocks.get(symbol)
    
    def cycle_to_next_symbol(self):
        """Cycle to the next stock symbol for display"""
        if self.config.stock_symbols:
            self.current_symbol_index = (self.current_symbol_index + 1) % len(self.config.stock_symbols)
            return self.get_current_display_stock()
        return None
    
    def get_all_stocks(self):
        """Get all cached stock data"""
        return self.stocks
    
    def get_stock(self, symbol):
        """Get data for a specific stock symbol"""
        return self.stocks.get(symbol)
    
    def is_market_open(self):
        """Check if the market is currently open (simplified check)"""
        now = datetime.now()
        
        # Basic US market hours check (9:30 AM - 4:00 PM ET, Mon-Fri)
        # This is a simplified check - real implementation would consider holidays
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        # Convert to approximate ET (this is simplified)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def format_price(self, price):
        """Format price for display"""
        if price is None:
            return "N/A"
        
        if price >= 1000:
            return f"${price:,.0f}"
        elif price >= 100:
            return f"${price:.0f}"
        elif price >= 10:
            return f"${price:.1f}"
        else:
            return f"${price:.2f}"
    
    def format_change(self, change, percent_change):
        """Format price change for display"""
        if change is None or percent_change is None:
            return ""
        
        change_str = f"{change:+.2f}"
        percent_str = f"{percent_change:+.1f}%"
        
        if change > 0:
            return f"▲{change_str} ({percent_str})"
        elif change < 0:
            return f"▼{abs(change):.2f} ({percent_str})"
        else:
            return f"={change_str} ({percent_str})"