from _typeshed import Incomplete
from enum import Enum

MAX_SUBSCRIPTIONS_PER_STREAM = int
WEBSOCKET_BASE_URI = str
WEBSOCKET_API_BASE_URI = str

class Exchanges(str, Enum):
    BINANCE = 'binance.com'
    BINANCE_TESTNET = 'binance.com-testnet'
    BINANCE_MARGIN = 'binance.com-margin'
    BINANCE_MARGIN_TESTNET = 'binance.com-margin-testnet'
    BINANCE_ISOLATED_MARGIN = 'binance.com-isolated_margin'
    BINANCE_ISOLATED_MARGIN_TESTNET = 'binance.com-isolated_margin-testnet'
    BINANCE_FUTURES = 'binance.com-futures'
    BINANCE_COIN_FUTURES = 'binance.com-coin_futures'
    BINANCE_FUTURES_TESTNET = 'binance.com-futures-testnet'
    BINANCE_US = 'binance.us'
    TRBINANCE = 'trbinance.com'
    BINANCE_ORG = 'binance.org'
    BINANCE_ORG_TESTNET = 'binance.org-testnet'

DEX_EXCHANGES: Incomplete
CEX_EXCHANGES: Incomplete
CONNECTION_SETTINGS: Incomplete
