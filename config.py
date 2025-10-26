# config.py

# Telegram settings (Replace with your actual tokens)
TELEGRAM_TOKEN = '8384616931:AAFBdhKNiub0-HJ7bgz_gYeTD_l4Ft8V7ik'  
CHAT_ID = '-1002771663242'  

# Trading settings
SYMBOLS = [
    'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 
    'AVAXUSDT', 'DOTUSDT', 'TRXUSDT', 'LTCUSDT', 'BCHUSDT',
    'ETCUSDT', 'UNIUSDT', 'FILUSDT', 'OPUSDT', 'APTUSDT', 
    'ATOMUSDT', 'XMRUSDT', 'HBARUSDT', 'AAVEUSDT', 
    'QNTUSDT', 'ARBUSDT', 'VETUSDT', 'GALAUSDT', 
    'SUIUSDT', 'MANAUSDT', 'AXSUSDT', 'SANDUSDT', 'ALGOUSDT', 
    'ZECUSDT', 'THETAUSDT', 'CHZUSDT', 'ICPUSDT', 
    'GRTUSDT', 'IMXUSDT', 'CRVUSDT', 'RUNEUSDT', 'INJUSDT', 'TIAUSDT'
]

INTERVAL = '1m'
BAND_MULT_3 = 3.1           # VWAP Bands at 3 standard deviations
CALC_MODE = 'Standard Deviation'
SESSION_DELAY_MIN = 30      # Delay signals for the first 30 mins of the UTC day
COOLDOWN_MIN = 30           # Cooldown period after a trade in one direction
STOPLOSS_PERCENT = 3.0      # Hard Stoploss at 3.0%
SAFETY_CHECK_INTERVAL_SEC = 300 # Backfill safety check every 5 minutes (300 seconds)