# web_server.py

from flask import Flask, jsonify
import threading
from datetime import datetime, timezone
import os

app = Flask(__name__)

# Global variable to track bot status
bot_status = {
    'started_at': None,
    'is_running': False,
    'last_signal': None,
    'signals_count': 0,
    'active_positions': 0
}

def update_bot_status(status_dict):
    """Update bot status from main script"""
    global bot_status
    bot_status.update(status_dict)

@app.route('/')
def home():
    """Root endpoint"""
    return jsonify({
        'status': 'online',
        'bot': 'VWAP Trading Bot',
        'version': '2.0'
    })

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    uptime = 0
    if bot_status['started_at']:
        uptime = (datetime.now(timezone.utc) - bot_status['started_at']).total_seconds()
    
    return jsonify({
        'status': 'healthy',
        'uptime_seconds': uptime,
        'is_running': bot_status['is_running'],
        'signals_today': bot_status['signals_count'],
        'active_positions': bot_status['active_positions'],
        'last_signal': bot_status['last_signal']
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return 'pong'

def start_web_server():
    """Start Flask server in background"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)