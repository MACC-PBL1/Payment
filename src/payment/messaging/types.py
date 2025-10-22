from typing import (
    Any,
    Callable,
    Dict,
)

type MessageType = Dict[str, Any]
type HandlerFunc = Callable[[MessageType], None]