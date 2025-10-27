# main.py

import time
import threading
from datetime import datetime, timezone
from binance import Client
from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager
import json
import os
from config import (
    TELEGRAM_TOKEN, CHAT_ID, SYMBOLS, INTERVAL, BAND_MULT_3, 
    CALC_MODE, SESSION_DELAY_MIN, COOLDOWN_MIN, STOPLOSS_PERCENT, 
    SAFETY_CHECK_INTERVAL_SEC
)
from bot import VWAPBot, SignalsCounter
from telegram_handler import TelegramCommandHandler

# Import web server
from web_server import start_web_server, update_bot_status

# Initialize
signal_counter = SignalsCounter()
client = Client(tld='com')

# Update bot status for web server
update_bot_status({
    'started_at': datetime.now(timezone.utc),
    'is_running': True
})

# Start web server in background thread (IMPORTANT: Start this first!)
web_thread = threading.Thread(target=start_web_server, daemon=True)
web_thread.start()
print("✓ Web server started for Render")

# Create bot instances
print(f"Initializing {len(SYMBOLS)} trading bots...")
bots = {
    symbol: VWAPBot(
        symbol, TELEGRAM_TOKEN, CHAT_ID, CALC_MODE, BAND_MULT_3, 
        SESSION_DELAY_MIN, COOLDOWN_MIN, signal_counter, STOPLOSS_PERCENT
    ) 
    for symbol in SYMBOLS
}

# WebSocket Manager
ubwa = BinanceWebSocketApiManager(
    exchange="binance.com-futures",
    high_performance=True,
    disable_colorama=True
)

# Initialize Telegram Command Handler
telegram_handler = TelegramCommandHandler(TELEGRAM_TOKEN, CHAT_ID, bots, ubwa, client)

def process_websocket_messages():
    """Optimized WebSocket message processor"""
    print("WebSocket processor started")
    
    while True:
        try:
            if ubwa.is_manager_stopping():
                break
            
            if not telegram_handler.is_running:
                time.sleep(0.1)
                continue
            
            # Process multiple messages in batch
            for _ in range(10):
                data = ubwa.pop_stream_data_from_stream_buffer()
                
                if not data:
                    break
                
                try:
                    # Handle dict or string data
                    if isinstance(data, str):
                        msg = json.loads(data)
                    else:
                        msg = data
                    
                    # Extract data
                    if isinstance(msg, dict):
                        if 'data' in msg:
                            data = msg['data']
                        else:
                            data = msg
                        
                        # Process closed klines only
                        if data.get('e') == 'kline':
                            kline = data.get('k', {})
                            
                            if kline.get('x'):  # Closed candle
                                symbol = kline.get('s')
                                bot = bots.get(symbol)
                                
                                if bot and bot.enabled:
                                    new_row = {
                                        'timestamp': datetime.fromtimestamp(kline['t'] / 1000, tz=timezone.utc),
                                        'Open': float(kline['o']),
                                        'High': float(kline['h']),
                                        'Low': float(kline['l']),
                                        'Close': float(kline['c']),
                                        'Volume': float(kline['v'])
                                    }
                                    bot.process_new_kline(new_row)
                                    
                                    # Update web server status
                                    active_positions = sum(1 for b in bots.values() if b.current_position != 'NONE')
                                    update_bot_status({
                                        'active_positions': active_positions,
                                        'signals_count': signal_counter.get_count()
                                    })
                            
                except Exception as e:
                    pass  # Silently handle parsing errors
            
            time.sleep(0.005)  # Small sleep between batches
                    
        except Exception as e:
            print(f"WebSocket error: {e}")
            time.sleep(1)

def periodic_safety_check():
    """Periodic backfill checker"""
    while True:
        try:
            time.sleep(SAFETY_CHECK_INTERVAL_SEC)
            
            if not telegram_handler.is_running:
                continue
            
            print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Backfill check...")
            
            for symbol, bot in bots.items():
                if bot.enabled:
                    bot.backfill_missing_klines(client)
                    time.sleep(0.2)  # Small delay between symbols
                
        except Exception as e:
            print(f"Backfill error: {e}")
            time.sleep(10)

def monitor_connection():
    """Connection monitor"""
    while True:
        try:
            time.sleep(120)
            
            buffer_length = ubwa.get_stream_buffer_length()
            
            if buffer_length > 10000:
                print(f"Clearing large buffer: {buffer_length}")
                ubwa.clear_stream_buffer()
            
            if buffer_length > 50000:
                print("Critical buffer size, restarting stream...")
                restart_stream()
                
        except Exception as e:
            pass

def create_stream():
    """Create WebSocket stream"""
    channels = ['kline_' + INTERVAL]
    markets = [symbol.lower() for symbol in SYMBOLS]
    
    stream_id = ubwa.create_stream(
        channels=channels,
        markets=markets,
        stream_label="VWAP_Stream"
    )
    
    print(f"Stream created: {stream_id}")
    return stream_id

def restart_stream():
    """Restart WebSocket stream"""
    try:
        for stream_id in ubwa.get_active_stream_list():
            ubwa.stop_stream(stream_id)
        time.sleep(2)
        ubwa.clear_stream_buffer()
        create_stream()
    except Exception as e:
        print(f"Restart error: {e}")

# MAIN EXECUTION
print("="*50)
print(f"VWAP Trading Bot v2.0")
print(f"Symbols: {len(SYMBOLS)}")
print(f"Port: {os.environ.get('PORT', 10000)}")
print("="*50)

# Load historical data
print("\nLoading historical data...")
for i, (symbol, bot) in enumerate(bots.items(), 1):
    print(f"[{i}/{len(bots)}] Loading {symbol}...", end='')
    bot.load_historical_data(client)
    print(" ✓")
    time.sleep(0.3)

# Create WebSocket stream
print("\nStarting WebSocket stream...")
stream_id = create_stream()
time.sleep(2)

# Start all threads
threads = []

# Telegram handler
t = threading.Thread(target=telegram_handler.run_telegram_bot, daemon=True)
t.start()
threads.append(t)

# WebSocket processor
t = threading.Thread(target=process_websocket_messages, daemon=True)
t.start()
threads.append(t)

# Backfill checker
t = threading.Thread(target=periodic_safety_check, daemon=True)
t.start()
threads.append(t)

# Connection monitor
t = threading.Thread(target=monitor_connection, daemon=True)
t.start()
threads.append(t)

print("\n" + "="*50)
print("✅ Bot Started Successfully!")
print(f"✅ Web server running on port {os.environ.get('PORT', 10000)}")
print(f"✅ All {len(threads)} services running")
print(f"✅ Telegram commands ready")
print("="*50)
print("\nSend /help to bot for commands")

# Keep main thread alive
try:
    while True:
        time.sleep(60)
        
        # Update web server status
        update_bot_status({
            'is_running': telegram_handler.is_running,
            'signals_count': signal_counter.get_count()
        })
        
        # Health check
        try:
            active_streams = len(ubwa.get_active_stream_list())
            if active_streams == 0 and telegram_handler.is_running:
                print("No active streams, restarting...")
                restart_stream()
        except:
            pass
            
except KeyboardInterrupt:
    print("\n\nShutting down...")
    ubwa.stop_manager()
    print("Bot stopped.")