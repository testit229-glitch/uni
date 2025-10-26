# telegram_handler.py

import psutil
import threading
import time
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry # ✅ Use this public path
class TelegramCommandHandler:
    def __init__(self, telegram_token, chat_id, bots, ubwa, client):
        self.telegram_token = telegram_token
        self.channel_id = chat_id  # This is for signals only
        self.bots = bots
        self.ubwa = ubwa
        self.client = client
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        self.last_update_id = None
        self.authorized_users = []
        self.bot_started_notified = False
        
        # Create session with retry logic
        self.session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504)
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
    def send_message(self, text, chat_id=None):
        """Send a message to specific chat or channel"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        target_chat = chat_id if chat_id else self.channel_id
        
        params = {
            'chat_id': target_chat,
            'text': text,
            'parse_mode': 'Markdown'
        }
        
        try:
            response = self.session.post(url, json=params, timeout=10)
            result = response.json()
            if not result.get('ok'):
                if 'Too Many Requests' in str(result):
                    time.sleep(5)  # Rate limit hit, wait
                else:
                    print(f"Telegram error: {result.get('description', 'Unknown')}")
            return result
        except requests.exceptions.Timeout:
            return None
        except Exception as e:
            print(f"Send message error: {e}")
            return None
    
    def get_updates(self):
        """Get updates from Telegram with proper timeout handling"""
        url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
        params = {
            'timeout': 25,  # Long polling timeout
            'allowed_updates': ['message', 'channel_post']
        }
        
        if self.last_update_id:
            params['offset'] = self.last_update_id + 1
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return data
            return None
            
        except requests.exceptions.ReadTimeout:
            # Normal for long polling, return None
            return None
        except requests.exceptions.ConnectionError:
            # Connection issue, wait and retry
            time.sleep(5)
            return None
        except Exception as e:
            if 'Read timed out' not in str(e):
                print(f"Get updates error: {e}")
            return None
    
    def handle_command(self, command, args, chat_id, username=None):
        """Handle incoming commands"""
        
        # Send startup message to first user (only once)
        if not self.bot_started_notified and chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.telegram_token}/getMe"
                response = self.session.get(url, timeout=5)
                if response.status_code == 200:
                    bot_info = response.json()
                    if bot_info.get('ok'):
                        bot_name = bot_info['result'].get('username', 'Unknown')
                        startup_msg = f"""🤖 **VWAP Bot Ready**
━━━━━━━━━━━━━━━
Bot: @{bot_name}
Status: 🟢 Online
User: @{username if username else 'User'}

Type /help for commands
━━━━━━━━━━━━━━━"""
                        self.send_message(startup_msg, chat_id)
                        self.bot_started_notified = True
            except:
                pass
        
        # Store authorized user
        if chat_id not in self.authorized_users:
            self.authorized_users.append(chat_id)
            print(f"Authorized user: @{username} (ID: {chat_id})")
        
        # Process commands
        if command == '/start' or command == '/run':
            if self.is_running:
                self.send_message("✅ Bot is already running!", chat_id)
            else:
                self.is_running = True
                for bot in self.bots.values():
                    bot.enabled = True
                self.send_message("🚀 Bot started successfully!", chat_id)
        
        elif command == '/stop':
            if not self.is_running:
                self.send_message("⚠️ Bot is already stopped!", chat_id)
            else:
                self.is_running = False
                for bot in self.bots.values():
                    bot.enabled = False
                self.send_message("🛑 Bot stopped! Use /start to resume.", chat_id)
        
        elif command == '/status':
            uptime = datetime.now(timezone.utc) - self.start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            
            active_positions = sum(1 for bot in self.bots.values() if bot.current_position != 'NONE')
            total_signals = self.bots[list(self.bots.keys())[0]].counter.get_count() if self.bots else 0
            
            long_count = sum(1 for bot in self.bots.values() if bot.current_position == 'LONG')
            short_count = sum(1 for bot in self.bots.values() if bot.current_position == 'SHORT')
            
            # Get stoploss from config
            from config import STOPLOSS_PERCENT
            
            try:
                active_streams = len(self.ubwa.get_active_stream_list())
                buffer_size = self.ubwa.get_stream_buffer_length()
                ws_status = "✅ Connected"
            except:
                ws_status = "❌ Disconnected"
                active_streams = 0
                buffer_size = 0
            
            status_msg = f"""📊 **STATUS**
━━━━━━━━━━━
🤖 Bot: {'🟢 Running' if self.is_running else '🔴 Stopped'}
⏱ Uptime: {int(hours)}h {int(minutes)}m
📈 Positions: {active_positions}
   • Longs: {long_count}
   • Shorts: {short_count}
📊 Signals: {total_signals}
🛑 Stoploss: {STOPLOSS_PERCENT}%
🌐 WS: {ws_status}
💾 Buffer: {buffer_size}
🪙 Symbols: {len(self.bots)}
━━━━━━━━━━━"""
            self.send_message(status_msg, chat_id)
        
        elif command == '/memory' or command == '/memry':
            # Get process info
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            process_cpu = process.cpu_percent(interval=0.5)
            
            # Get system memory
            system_memory = psutil.virtual_memory()
            
            combined_msg = f"""⚡ **CPU USAGE**
━━━━━━━━━━━━━━━
🤖 Bot: {process_cpu:.1f}%
💻 System: {cpu_percent:.1f}%
━━━━━━━━━━━━━━━
💾 **MEMORY USAGE**
━━━━━━━━━━━━━━━
🤖 Bot: {memory_mb:.1f} MB
📊 System: {system_memory.percent:.1f}%
💻 Available: {system_memory.available/1024/1024/1024:.1f} GB
📁 Total: {system_memory.total/1024/1024/1024:.1f} GB
━━━━━━━━━━━━━━━"""
            self.send_message(combined_msg, chat_id)
        
        elif command == '/list':
            if not self.bots:
                self.send_message("No symbols!", chat_id)
                return
            
            msg = "**Active Symbols:**\n"
            for symbol, bot in sorted(self.bots.items()):
                emoji = {'LONG': '🟢', 'SHORT': '🔴', 'NONE': '⚪'}.get(bot.current_position, '⚪')
                if bot.current_position != 'NONE' and bot.entry_price:
                    msg += f"{emoji} {symbol} @ {bot.entry_price:.4f}\n"
                else:
                    msg += f"{emoji} {symbol}\n"
                
                if len(msg) > 3000:
                    self.send_message(msg, chat_id)
                    msg = ""
                    time.sleep(0.5)
            
            if msg:
                self.send_message(msg, chat_id)
        
        elif command == '/positions' or command == '/pos':
            positions = [(s, b) for s, b in self.bots.items() if b.current_position != 'NONE']
            
            if not positions:
                self.send_message("📊 No active positions", chat_id)
            else:
                msg = f"**Positions ({len(positions)}):**\n\n"
                for symbol, bot in positions:
                    emoji = '🟢' if bot.current_position == 'LONG' else '🔴'
                    msg += f"{emoji} {symbol}\n"
                    msg += f"Entry: {bot.entry_price:.4f}\n"
                    msg += f"SL: {bot.stoploss_price:.4f}\n\n"
                self.send_message(msg, chat_id)
        
        elif command == '/settings':
            from config import INTERVAL, BAND_MULT_3, CALC_MODE, SESSION_DELAY_MIN, COOLDOWN_MIN, STOPLOSS_PERCENT, SAFETY_CHECK_INTERVAL_SEC
            
            settings_msg = f"""⚙️ **SETTINGS**
━━━━━━━━━━━━━━━
📊 Interval: {INTERVAL}
📈 Band Mult: {BAND_MULT_3}x
📐 Mode: {CALC_MODE}
⏱ Session Delay: {SESSION_DELAY_MIN}m
⏸ Cooldown: {COOLDOWN_MIN}m
🛑 Stoploss: {STOPLOSS_PERCENT}%
🔄 Backfill: {SAFETY_CHECK_INTERVAL_SEC}s
━━━━━━━━━━━━━━━"""
            self.send_message(settings_msg, chat_id)
        
        elif command == '/cpu':
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            process = psutil.Process()
            process_cpu = process.cpu_percent(interval=0.5)
            
            cpu_msg = f"""⚡ **CPU USAGE**
━━━━━━━━━━━━━━━
🤖 Bot: {process_cpu:.1f}%
💻 System: {cpu_percent:.1f}%
🔢 Cores: {cpu_count}
━━━━━━━━━━━━━━━"""
            self.send_message(cpu_msg, chat_id)
        
        elif command == '/mem':
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            system_memory = psutil.virtual_memory()
            
            mem_msg = f"""💾 **MEMORY USAGE**
━━━━━━━━━━━━━━━
🤖 Bot: {memory_mb:.1f} MB
📊 System: {system_memory.percent:.1f}%
💻 Available: {system_memory.available/1024/1024/1024:.1f} GB
📁 Total: {system_memory.total/1024/1024/1024:.1f} GB
━━━━━━━━━━━━━━━"""
            self.send_message(mem_msg, chat_id)
        
        elif command == '/help':
            help_msg = """📚 **COMMANDS**
━━━━━━━━━━━
/start - Start bot
/stop - Stop bot
/status - Full status
/positions - Active trades
/list - All symbols
/settings - Bot settings
/memory - CPU & Memory
/cpu - CPU usage only
/mem - Memory only
/help - This help
━━━━━━━━━━━"""
            self.send_message(help_msg, chat_id)
        
        else:
            self.send_message(f"Unknown: {command}\n/help for commands", chat_id)
    
    def run_telegram_bot(self):
        """Run the telegram bot polling loop with robust error handling"""
        print("Starting Telegram handler...")
        
        # Get bot info
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/getMe"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    bot_name = bot_info['result'].get('username', 'Unknown')
                    print(f"✓ Telegram bot ready: @{bot_name}")
        except Exception as e:
            print(f"Bot info error: {e}")
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:
            try:
                updates = self.get_updates()
                
                if updates and updates.get('ok'):
                    consecutive_errors = 0  # Reset on success
                    
                    for update in updates.get('result', []):
                        self.last_update_id = update.get('update_id')
                        
                        message = update.get('message') or update.get('channel_post')
                        if message:
                            text = message.get('text', '')
                            chat = message.get('chat', {})
                            chat_id = chat.get('id')
                            
                            from_user = message.get('from', {})
                            username = from_user.get('username', 'Unknown')
                            
                            if text.startswith('/'):
                                command = text.split()[0].split('@')[0]
                                args = text.split()[1:] if len(text.split()) > 1 else []
                                print(f"Command: {command} from @{username}")
                                self.handle_command(command, args, chat_id, username)
                
                time.sleep(0.5)
                
            except KeyboardInterrupt:
                break
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors > max_consecutive_errors:
                    print(f"Too many errors, waiting 60s...")
                    time.sleep(60)
                    consecutive_errors = 0
                else:
                    time.sleep(5)