from .listener import RabbitMQListener
from .types import (
    HandlerFunc,
    MessageType,
)
from typing import (
    Any,
    Callable,
    Dict,
    LiteralString,
)
import logging

# Global Variables ############################################################
logger = logging.getLogger(__name__)
QUEUE_HANDLERS: Dict[str, HandlerFunc] = {}

# Functions ###################################################################
def register_queue_handler(
    queue: LiteralString
) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to register event handlers"""
    def decorator(func: HandlerFunc) -> HandlerFunc:
        QUEUE_HANDLERS[queue] = func
        logger.info(f"Registered handler for queue: {queue}")
        return func
    return decorator

def process_message(message: MessageType, queue: str):
    """Process incoming RabbitMQ messages."""
    try:
        QUEUE_HANDLERS[queue](message)
    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)
        raise

def start_rabbitmq_listener(
    queue: str,
    config: Dict[str, Any],
) -> None:
    """Start RabbitMQ listener in a separate thread."""
    try:
        with RabbitMQListener(
            host=config.get("host", "localhost"),
            port=config.get("port", 5672),
            username=config.get("username", "guest"),
            password=config.get("password", "guest"),
            queue=queue,
            use_tls=config.get("use_tls", False),
            ca_cert=config.get("ca_cert_path", None),
            client_cert=config.get("client_cert_path", None),
            client_key=config.get("client_key_path", None),
            prefetch_count=config.get("prefetch_count", 10)
        ) as listener:
            logger.info(
                f"RabbitMQ listener connected to queue: {queue}"
            )
            listener.consume(process_message)
    except KeyboardInterrupt:
        logger.info("RabbitMQ listener stopped by keyboard interrupt")
    except Exception as e:
        logger.error(f"RabbitMQ listener error: {e}", exc_info=True)