# bot.py

import pandas as pd
import numpy as np 
import requests
from datetime import datetime, timezone
import threading
import time
from collections import defaultdict

class SignalsCounter:
    """Tracks the total signals generated today (resets daily at UTC 00:00)."""
    def __init__(self):
        self.count = 0
        self.last_reset_date = None
        self.lock = threading.Lock()

    def get_count(self):
        with self.lock:
            current_date = datetime.now(timezone.utc).date()
            if self.last_reset_date != current_date:
                self.count = 0
                self.last_reset_date = current_date
            return self.count

    def increment(self, count=1):
        with self.lock:
            self.count += count
            return self.count

class SignalBatcher:
    """Batches multiple signals into single messages"""
    def __init__(self, telegram_token, chat_id, batch_window=2.0):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.batch_window = batch_window  # seconds to wait for batching
        self.pending_signals = []
        self.pending_exits = []
        self.pending_stoploss = []
        self.lock = threading.Lock()
        self.timer = None
        
    def add_signal(self, signal_type, symbol, entry_price, stoploss_price, band_type=None, 
                   exit_price=None, peak_profit=None, reason=None):
        """Add a signal to the batch"""
        with self.lock:
            signal_data = {
                'symbol': symbol,
                'entry_price': entry_price,
                'stoploss_price': stoploss_price,
                'band_type': band_type,
                'exit_price': exit_price,
                'peak_profit': peak_profit,
                'reason': reason,
                'time': datetime.now(timezone.utc)
            }
            
            if signal_type in ['BUY', 'SELL', '2ND BUY', '2ND SELL']:
                self.pending_signals.append((signal_type, signal_data))
            elif signal_type in ['EXIT LONG', 'EXIT SHORT', 'TP1']:
                self.pending_exits.append((signal_type, signal_data))
            elif signal_type == 'STOPLOSS':
                self.pending_stoploss.append((signal_type, signal_data))
            
            # Start or reset timer
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.batch_window, self._send_batch)
            self.timer.start()
    
    def _send_batch(self):
        """Send all pending signals as a single message"""
        with self.lock:
            if not self.pending_signals and not self.pending_exits and not self.pending_stoploss:
                return
            
            current_time = datetime.now(timezone.utc).strftime('%H:%M:%S')
            message_parts = []
            
            # Process regular signals (BUY/SELL)
            if self.pending_signals:
                message_parts.append("📣 *SIGNALS DETECTED*\n━━━━━━━━━━━━━━━━━━\n")
                
                buy_signals = [(s, d) for s, d in self.pending_signals if 'BUY' in s]
                sell_signals = [(s, d) for s, d in self.pending_signals if 'SELL' in s]
                
                counter = 1
                
                # Add BUY signals
                for signal_type, data in buy_signals:
                    emoji = "🟢" if signal_type == "BUY" else "🟢🟢"
                    label = "BUY" if signal_type == "BUY" else "2ND BUY"
                    message_parts.append(
                        f"{counter}. {emoji} *{label} #{data['symbol']}*\n"
                        f"   Entry: {data['entry_price']:.4f}\n"
                        f"   SL: {data['stoploss_price']:.4f}\n\n"
                    )
                    counter += 1
                
                # Add SELL signals
                for signal_type, data in sell_signals:
                    emoji = "🔴" if signal_type == "SELL" else "🔴🔴"
                    label = "SELL" if signal_type == "SELL" else "2ND SELL"
                    message_parts.append(
                        f"{counter}. {emoji} *{label} #{data['symbol']}*\n"
                        f"   Entry: {data['entry_price']:.4f}\n"
                        f"   SL: {data['stoploss_price']:.4f}\n\n"
                    )
                    counter += 1
            
            # Process EXIT signals
            if self.pending_exits:
                if message_parts:
                    message_parts.append("━━━━━━━━━━━━━━━━━━\n")
                message_parts.append("🔔 *EXIT REPORTS*\n━━━━━━━━━━━━━━━━━━\n")
                
                counter = 1
                for signal_type, data in self.pending_exits:
                    emoji = "🟡"
                    if 'TP1' in signal_type:
                        label = "TP1"
                    else:
                        label = signal_type
                    
                    message_parts.append(
                        f"{counter}. {emoji} *{label} #{data['symbol']}*\n"
                    )
                    
                    if data['peak_profit'] is not None:
                        message_parts.append(f"   Peak: {data['peak_profit']:.2f}%\n")
                    if data['exit_price'] is not None:
                        message_parts.append(f"   Exit: {data['exit_price']:.4f}\n")
                    if data['reason']:
                        message_parts.append(f"   Reason: {data['reason']}\n")
                    
                    message_parts.append("\n")
                    counter += 1
            
            # Process STOPLOSS signals
            if self.pending_stoploss:
                if message_parts:
                    message_parts.append("━━━━━━━━━━━━━━━━━━\n")
                message_parts.append("🛑 *STOPLOSS HIT*\n━━━━━━━━━━━━━━━━━━\n")
                
                counter = 1
                for signal_type, data in self.pending_stoploss:
                    message_parts.append(
                        f"{counter}. *#{data['symbol']}*\n"
                        f"   Entry: {data['entry_price']:.4f}\n"
                        f"   Exit: {data['stoploss_price']:.4f}\n"
                    )
                    if data['peak_profit'] is not None:
                        message_parts.append(f"   Peak: {data['peak_profit']:.2f}%\n")
                    message_parts.append("\n")
                    counter += 1
            
            # Add footer
            message_parts.append(f"━━━━━━━━━━━━━━━━━━\n⏰ Time: {current_time} UTC")
            
            # Send the message
            full_message = ''.join(message_parts)
            self._send_telegram_message(full_message)
            
            # Clear pending signals
            self.pending_signals.clear()
            self.pending_exits.clear()
            self.pending_stoploss.clear()
    
    def _send_telegram_message(self, message):
        """Send message to Telegram"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        params = {'chat_id': self.chat_id, 'text': message, 'parse_mode': 'Markdown'}
        try:
            response = requests.post(url, json=params, timeout=10)
            if response.status_code == 200:
                print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Batch signal sent ({len(message)} chars)")
        except Exception as e:
            print(f"Error sending batch signal: {e}")

# Global signal batcher (will be initialized in VWAPBot)
signal_batcher = None

class VWAPBot:
    def __init__(self, symbol, telegram_token, chat_id, calc_mode, band_mult_3, session_delay_min, cooldown_min, counter, stoploss_percent):
        global signal_batcher
        
        self.symbol = symbol
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.calc_mode = calc_mode
        self.band_mult_3 = band_mult_3
        self.session_delay_min = session_delay_min 
        self.cooldown_min = cooldown_min
        self.counter = counter
        self.stoploss_percent = stoploss_percent
        
        # Initialize signal batcher (only once)
        if signal_batcher is None:
            signal_batcher = SignalBatcher(telegram_token, chat_id, batch_window=2.0)
        
        # Control flag for Telegram commands
        self.enabled = True
        
        # Position Tracking
        self.current_position = 'NONE'
        self.entry_price = None
        self.stoploss_price = None
        self.peak_profit_percent = 0.0
        
        # Cooldown Tracking
        self.last_buy_time = None
        self.last_sell_time = None
        
        # DataFrame and VWAP state
        self.df = None 
        self.last_vwap_reset_date = None
        self.max_bars = 1440 # Keep only last 1440 bars in memory
        
        # Incremental VWAP variables
        self.cum_vol = np.float64(0.0)
        self.cum_pv = np.float64(0.0)
        self.cum_var = np.float64(0.0)
        self.vwap = None
        self.stdev = None
        
        # Threading Lock
        self.lock = threading.Lock()

    def send_telegram_message(self, message):
        """Legacy method for compatibility - now uses batching"""
        # Parse the message to extract signal details and add to batcher
        # This is a simplified parser - you might need to adjust based on your exact message format
        pass  # Signals are now sent through check_signal directly to batcher

    def load_historical_data(self, client):
        """Loads historical 1m data from 00:00 UTC for initial VWAP state."""
        with self.lock:
            try:
                current_time = datetime.now(timezone.utc)
                session_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                since = int(session_start.timestamp() * 1000)
                
                klines = []
                start_time = since
                
                while True:
                    new_klines = client.futures_klines(symbol=self.symbol, interval='1m', startTime=start_time, limit=1000)
                    if not new_klines:
                        break
                    klines.extend(new_klines)
                    start_time = new_klines[-1][0] + 1
                    
                    # Limit historical data to avoid memory issues
                    if len(klines) > self.max_bars:
                        klines = klines[-self.max_bars:]
                        break
                
                if not klines:
                    print(f"[{self.symbol}] No historical data found")
                    self.df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
                    self.df.index.name = 'timestamp'
                    self.last_vwap_reset_date = current_time.date()
                    return
                
                # Prepare DataFrame
                self.df = pd.DataFrame(klines, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 
                                                        'close_time', 'quote_asset_volume', 'number_of_trades', 
                                                        'taker_buy_base', 'taker_buy_quote', 'ignore'])
                self.df = self.df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
                self.df['timestamp'] = pd.to_datetime(self.df['timestamp'], unit='ms', utc=True)
                self.df.set_index('timestamp', inplace=True)
                self.df = self.df.astype(np.float64)
                
                # Initialize incremental VWAP from historical data
                self._initialize_vwap_from_dataframe()
                
                self.last_vwap_reset_date = self.df.index[-1].date()
                
                vwap_str = f"{self.vwap:.4f}" if self.vwap is not None else "N/A"
                print(f"[{self.symbol}] Loaded {len(self.df)} bars. VWAP: {vwap_str}")
                
            except Exception as e:
                print(f"[{self.symbol}] Error loading data: {e}")
                self.df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
                self.df.index.name = 'timestamp'

    def _initialize_vwap_from_dataframe(self):
        """Initialize incremental VWAP variables from DataFrame."""
        if self.df is None or len(self.df) == 0:
            return
            
        # Calculate typical price for all bars
        tp = (self.df['High'] + self.df['Low'] + self.df['Close']) / 3.0
        pv = tp * self.df['Volume']
        
        # Cumulative values
        self.cum_pv = pv.sum()
        self.cum_vol = self.df['Volume'].sum()
        
        # VWAP
        if self.cum_vol > 0:
            self.vwap = self.cum_pv / self.cum_vol
            
            # Variance for standard deviation
            dev = tp - self.vwap
            var_contrib = self.df['Volume'] * (dev ** 2)
            self.cum_var = var_contrib.sum()
            
            vwap_variance = self.cum_var / self.cum_vol
            self.stdev = np.sqrt(vwap_variance)
        else:
            self.vwap = None
            self.stdev = None

    def reset_vwap_state(self, new_bar_timestamp):
        """Resets VWAP state at the start of a new UTC day."""
        print(f"[{self.symbol}] Daily VWAP reset")
        
        # Clear DataFrame
        self.df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'])
        self.df.index.name = 'timestamp'
        
        # Reset incremental variables
        self.cum_vol = np.float64(0.0)
        self.cum_pv = np.float64(0.0)
        self.cum_var = np.float64(0.0)
        self.vwap = None
        self.stdev = None
        
        self.last_vwap_reset_date = new_bar_timestamp.date()

    def update_vwap_incremental(self, open_val, high_val, low_val, close_val, volume):
        """Update VWAP incrementally with new bar data."""
        if volume <= 0:
            return
            
        # Typical price
        tp = (high_val + low_val + close_val) / 3.0
        pv = tp * volume
        
        # Update cumulative values
        self.cum_pv += pv
        self.cum_vol += volume
        
        # Calculate new VWAP
        if self.cum_vol > 0:
            self.vwap = self.cum_pv / self.cum_vol
            
            # Update variance
            dev = tp - self.vwap
            var_contrib = volume * (dev ** 2)
            self.cum_var += var_contrib
            
            vwap_variance = self.cum_var / self.cum_vol
            self.stdev = np.sqrt(vwap_variance) if vwap_variance > 0 else 0.0

    def calculate_bands(self):
        """Calculate VWAP bands based on current state."""
        if self.vwap is None or self.stdev is None:
            return None, None, None
            
        band_basis = self.stdev if self.calc_mode == 'Standard Deviation' else self.vwap * 0.01
        upper_band_3 = self.vwap + band_basis * self.band_mult_3
        lower_band_3 = self.vwap - band_basis * self.band_mult_3
        
        return self.vwap, upper_band_3, lower_band_3

    def process_new_kline(self, new_row):
        """Process new closed kline and check for signals."""
        with self.lock:
            if self.df is None:
                return
            
            new_bar_timestamp = new_row['timestamp']
            
            # Skip duplicates
            if len(self.df) > 0 and new_bar_timestamp in self.df.index:
                return
            
            current_date_utc = new_bar_timestamp.date()
            
            # Daily reset check
            if self.last_vwap_reset_date is None or self.last_vwap_reset_date < current_date_utc:
                self.reset_vwap_state(new_bar_timestamp)
            
            try:
                # Add new bar to DataFrame
                new_df = pd.DataFrame([new_row])
                new_df.set_index('timestamp', inplace=True)
                new_df = new_df.astype(np.float64)
                
                # Concatenate
                self.df = pd.concat([self.df, new_df], ignore_index=False)
                
                # Keep only last N bars to save memory
                if len(self.df) > self.max_bars:
                    self.df = self.df.iloc[-self.max_bars:]
                
                # Update VWAP incrementally
                self.update_vwap_incremental(
                    new_row['Open'], 
                    new_row['High'], 
                    new_row['Low'], 
                    new_row['Close'], 
                    new_row['Volume']
                )
                
                # Check for signals
                self.check_signal()
                
            except Exception as e:
                print(f"[{self.symbol}] Error processing kline: {e}")

    def backfill_missing_klines(self, client):
        """Backfill missing klines using REST API."""
        with self.lock:
            if self.df is None or len(self.df) == 0:
                return
            
            try:
                last_kline_time_ms = int(self.df.index[-1].timestamp() * 1000)
                start_fetch_time_ms = last_kline_time_ms + 60000
                current_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                
                # Only backfill if we're more than 1 minute behind
                if start_fetch_time_ms < (current_time_ms - 70000):
                    missing_klines = client.futures_klines(
                        symbol=self.symbol,
                        interval='1m',
                        startTime=start_fetch_time_ms,
                        limit=50
                    )
                    
                    if missing_klines:
                        for kline in missing_klines:
                            if kline[6] < current_time_ms:
                                new_row = {
                                    'timestamp': datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                                    'Open': float(kline[1]),
                                    'High': float(kline[2]),
                                    'Low': float(kline[3]),
                                    'Close': float(kline[4]),
                                    'Volume': float(kline[5])
                                }
                                
                                # Process if not duplicate
                                if new_row['timestamp'] not in self.df.index:
                                    self.process_new_kline(new_row)
                                    
            except Exception as e:
                pass  # Silently handle backfill errors

    def check_signal(self):
        """Core trading logic: checks for signals."""
        global signal_batcher
        
        # Check if bot is enabled
        if not self.enabled:
            return
            
        if self.df is None or len(self.df) == 0:
            return
            
        vwap_val, upper_band_3, lower_band_3 = self.calculate_bands()
        
        if vwap_val is None:
            return
        
        current_bar = self.df.iloc[-1]
        current_close = current_bar['Close']
        low_val = current_bar['Low']
        high_val = current_bar['High']
        current_time = self.df.index[-1].to_pydatetime()
        
        # Track peak profit
        if self.current_position != 'NONE' and self.entry_price is not None:
            if self.current_position == 'LONG':
                current_profit_percent = ((current_close - self.entry_price) / self.entry_price) * 100.0
            elif self.current_position == 'SHORT':
                current_profit_percent = ((self.entry_price - current_close) / self.entry_price) * 100.0
            
            if current_profit_percent > self.peak_profit_percent:
                self.peak_profit_percent = current_profit_percent

        # Stoploss Check
        if self.current_position != 'NONE' and self.stoploss_price is not None:
            stoploss_hit = False
            direction = None
            
            if self.current_position == 'LONG' and low_val <= self.stoploss_price:
                stoploss_hit = True
                direction = "LONG"
            elif self.current_position == 'SHORT' and high_val >= self.stoploss_price:
                stoploss_hit = True
                direction = "SHORT"
            
            if stoploss_hit:
                signal_batcher.add_signal(
                    'STOPLOSS',
                    self.symbol,
                    self.entry_price,
                    self.stoploss_price,
                    peak_profit=self.peak_profit_percent
                )
                
                print(f"{direction} Stoploss Hit for {self.symbol}")
                self.current_position = 'NONE'
                self.entry_price = None
                self.stoploss_price = None
                self.peak_profit_percent = 0.0
                return

        # Check session delay
        session_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        time_since_session_start = (current_time - session_start).total_seconds() / 60
        suppress_signals = time_since_session_start < self.session_delay_min

        # Check cooldowns
        cooldown_passed_buy = self.last_buy_time is None or (current_time - self.last_buy_time).total_seconds() >= (self.cooldown_min * 60)
        cooldown_passed_sell = self.last_sell_time is None or (current_time - self.last_sell_time).total_seconds() >= (self.cooldown_min * 60)

        # Signal conditions
        buy_condition = low_val <= lower_band_3
        sell_condition = high_val >= upper_band_3

        # Scale-In Check for SHORT
        if (self.current_position == 'SHORT' and not suppress_signals and 
            sell_condition and cooldown_passed_sell and self.entry_price is not None):
            
            min_profit_price = self.entry_price * 0.99
            
            if current_close <= min_profit_price:
                # Exit with TP1
                signal_batcher.add_signal(
                    'TP1',
                    self.symbol,
                    self.entry_price,
                    None,
                    exit_price=current_close,
                    peak_profit=self.peak_profit_percent,
                    reason='Scale-In SHORT'
                )
                self.peak_profit_percent = 0.0

                # New SHORT position
                entry_price = upper_band_3
                stoploss_price = entry_price * (1 + self.stoploss_percent / 100)
                
                signal_batcher.add_signal(
                    '2ND SELL',
                    self.symbol,
                    entry_price,
                    stoploss_price,
                    band_type='upper'
                )

                self.last_sell_time = current_time
                self.current_position = 'SHORT'
                self.entry_price = entry_price
                self.stoploss_price = stoploss_price
                self.counter.increment()
                print(f"2ND SELL signal for {self.symbol}")
                return

        # Scale-In Check for LONG
        elif (self.current_position == 'LONG' and not suppress_signals and 
              buy_condition and cooldown_passed_buy and self.entry_price is not None):
            
            min_profit_price = self.entry_price * 1.01
            
            if current_close >= min_profit_price:
                # Exit with TP1
                signal_batcher.add_signal(
                    'TP1',
                    self.symbol,
                    self.entry_price,
                    None,
                    exit_price=current_close,
                    peak_profit=self.peak_profit_percent,
                    reason='Scale-In LONG'
                )
                self.peak_profit_percent = 0.0

                # New LONG position
                entry_price = lower_band_3
                stoploss_price = entry_price * (1 - self.stoploss_percent / 100)
                
                signal_batcher.add_signal(
                    '2ND BUY',
                    self.symbol,
                    entry_price,
                    stoploss_price,
                    band_type='lower'
                )

                self.last_buy_time = current_time
                self.current_position = 'LONG'
                self.entry_price = entry_price
                self.stoploss_price = stoploss_price
                self.counter.increment()
                print(f"2ND BUY signal for {self.symbol}")
                return

        # New Entry (No Position)
        if self.current_position == 'NONE' and not suppress_signals:
            if buy_condition and cooldown_passed_buy:
                # LONG Entry
                entry_price = lower_band_3
                stoploss_price = entry_price * (1 - self.stoploss_percent / 100)
                
                signal_batcher.add_signal(
                    'BUY',
                    self.symbol,
                    entry_price,
                    stoploss_price,
                    band_type='lower'
                )
                
                self.last_buy_time = current_time
                self.current_position = 'LONG'
                self.entry_price = entry_price
                self.stoploss_price = stoploss_price
                self.counter.increment()
                self.peak_profit_percent = 0.0
                print(f"BUY signal for {self.symbol}")

            elif sell_condition and cooldown_passed_sell:
                # SHORT Entry
                entry_price = upper_band_3
                stoploss_price = entry_price * (1 + self.stoploss_percent / 100)

                signal_batcher.add_signal(
                    'SELL',
                    self.symbol,
                    entry_price,
                    stoploss_price,
                    band_type='upper'
                )

                self.last_sell_time = current_time
                self.current_position = 'SHORT'
                self.entry_price = entry_price
                self.stoploss_price = stoploss_price
                self.counter.increment()
                self.peak_profit_percent = 0.0
                print(f"SELL signal for {self.symbol}")

        # Reversal: LONG to SHORT
        elif self.current_position == 'LONG' and sell_condition and not suppress_signals:
            # Exit LONG
            signal_batcher.add_signal(
                'EXIT LONG',
                self.symbol,
                self.entry_price,
                None,
                exit_price=current_close,
                peak_profit=self.peak_profit_percent,
                reason='Opposite Signal'
            )
            self.peak_profit_percent = 0.0
            
            # New SHORT
            entry_price = upper_band_3
            stoploss_price = entry_price * (1 + self.stoploss_percent / 100)
            
            signal_batcher.add_signal(
                'SELL',
                self.symbol,
                entry_price,
                stoploss_price,
                band_type='upper'
            )

            self.last_sell_time = current_time
            self.current_position = 'SHORT'
            self.entry_price = entry_price
            self.stoploss_price = stoploss_price
            self.counter.increment()
            print(f"REVERSAL to SELL for {self.symbol}")

        # Reversal: SHORT to LONG
        elif self.current_position == 'SHORT' and buy_condition and not suppress_signals:
            # Exit SHORT
            signal_batcher.add_signal(
                'EXIT SHORT',
                self.symbol,
                self.entry_price,
                None,
                exit_price=current_close,
                peak_profit=self.peak_profit_percent,
                reason='Opposite Signal'
            )
            self.peak_profit_percent = 0.0
            
            # New LONG
            entry_price = lower_band_3
            stoploss_price = entry_price * (1 - self.stoploss_percent / 100)

            signal_batcher.add_signal(
                'BUY',
                self.symbol,
                entry_price,
                stoploss_price,
                band_type='lower'
            )

            self.last_buy_time = current_time
            self.current_position = 'LONG'
            self.entry_price = entry_price
            self.stoploss_price = stoploss_price
            self.counter.increment()
            print(f"REVERSAL to BUY for {self.symbol}")