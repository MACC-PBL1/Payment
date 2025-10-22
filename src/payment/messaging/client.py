from pathlib import Path
from pika import (
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
    SSLOptions,
)
from pika.adapters.blocking_connection import BlockingChannel
from types import TracebackType
from typing import (
    LiteralString,
    Optional,
    Type,
)
import ssl

class RabbitMQBaseClient:
    _CONTENT_TYPE: LiteralString = "application/json"

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
        prefetch_count: int = 1,
    ) -> None:
        self._queue = queue
        self._prefetch_count = prefetch_count
        self._connection: Optional[BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
        
        # Create credentials
        credentials = PlainCredentials(username, password)
        
        # Configure TLS if enabled
        if use_tls:
            ssl_context = ssl.create_default_context(
                purpose=ssl.Purpose.CLIENT_AUTH,
                cafile=str(ca_cert) if ca_cert else None
            )
            
            # Load client certificate if provided
            if client_cert and client_key:
                ssl_context.load_cert_chain(
                    certfile=str(client_cert),
                    keyfile=str(client_key)
                )
            
            # For development, you might want to disable hostname checking
            # ssl_context.check_hostname = False
            # ssl_context.verify_mode = ssl.CERT_NONE
            
            ssl_options = SSLOptions(ssl_context, host)
        else:
            ssl_options = None
        
        # Create connection parameters
        self._params = ConnectionParameters(
            host=host,
            port=port,
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=600,
            blocked_connection_timeout=300,
        )

    def __enter__(self):
        """Context manager entry."""
        self._connect()
        return self
    
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Context manager exit."""
        self._close()
        return None

    def _connect(self) -> None:
        """Establish connection to RabbitMQ"""
        self._connection = BlockingConnection(self._params)
        self._channel = self._connection.channel()
        
        # Set QoS (prefetch count)
        self._channel.basic_qos(prefetch_count=self._prefetch_count)
        
        # Declare queue (idempotent)
        self._channel.queue_declare(
            queue=self._queue, 
            durable=True
        )

    def _close(self) -> None:
        """Close connection"""
        if self._connection and not self._connection.is_closed:
            self._connection.close()