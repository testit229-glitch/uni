from _typeshed import Incomplete

class MaximumSubscriptionsExceeded(Exception):
    message: Incomplete
    def __init__(self, exchange: str = None, max_subscriptions_per_stream: int = None) -> None: ...

class Socks5ProxyConnectionError(Exception): ...

class StreamIsCrashing(Exception):
    message: Incomplete
    def __init__(self, stream_id: Incomplete | None = None, reason: Incomplete | None = None) -> None: ...

class StreamIsRestarting(Exception):
    message: Incomplete
    def __init__(self, stream_id: Incomplete | None = None, reason: Incomplete | None = None) -> None: ...

class StreamIsStopping(Exception):
    message: Incomplete
    def __init__(self, stream_id: Incomplete | None = None, reason: Incomplete | None = None) -> None: ...

class UnknownExchange(Exception):
    def __init__(self, error_msg: Incomplete | None = None) -> None: ...
