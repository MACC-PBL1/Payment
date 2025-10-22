from .client import RabbitMQBaseClient
from .types import MessageType
from pathlib import Path
from pika import BasicProperties
from typing import (
    Any,
    Dict,
    Optional, 
)
import json

class RabbitMQPublisher(RabbitMQBaseClient):
    """RabbitMQ publisher with TLS support"""
    def __init__(
        self,
        host: str,
        port: int,  # Default TLS port
        username: str = "guest",
        password: str = "guest",
        queue: str = "my_queue",
        use_tls: bool = True,
        ca_cert: Optional[Path] = None,
        client_cert: Optional[Path] = None,
        client_key: Optional[Path] = None,
        prefetch_count: int = 1
    ) -> None:
        super().__init__(
            host, 
            port, 
            username, 
            password, 
            queue, 
            use_tls, 
            ca_cert, 
            client_cert, 
            client_key, 
            prefetch_count
        )

    def publish(
        self,
        message: MessageType,
        exchange: Optional[str] = None,
        persistent: bool = True,
    ) -> None:
        """
        Publish a message to RabbitMQ.
        
        Args:
            routing_key: Routing key (queue name for default exchange)
            message: Message to publish (will be JSON serialized if dict/list)
            exchange: Exchange name (uses instance default if None)
            persistent: Whether message should survive broker restart
        """
        if self._channel is None:
            raise RuntimeError("Not connected. Make sure it is connected.")
        
        # Serialize message
        body = json.dumps(message)
        
        # Message properties
        properties = BasicProperties(
            content_type=super()._CONTENT_TYPE,
            delivery_mode=2 if persistent else 1,
        )

        # Publish message
        self._channel.basic_publish(
            exchange=exchange if exchange is not None else "",
            routing_key=self._queue,
            body=body,
            properties=properties,
        )