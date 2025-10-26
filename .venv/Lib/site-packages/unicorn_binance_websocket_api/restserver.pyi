import logging
from _typeshed import Incomplete
from flask_restful import Resource

__logger__: logging.getLogger
logger = __logger__

class BinanceWebSocketApiRestServer(Resource):
    manager: Incomplete
    warn_on_update: Incomplete
    def __init__(self, handler_binance_websocket_api_manager, warn_on_update: bool = True) -> None: ...
    def get(self, statusformat, checkcommandversion: bool = False): ...
