from chassis.messaging import RabbitMQConfig
from pathlib import Path
from typing import (
    Dict,
    LiteralString,
    Optional,
)
import os

# RabbitMQ Configuration ###########################################################################
RABBITMQ_CONFIG: RabbitMQConfig = {
    "host": os.getenv("RABBITMQ_HOST", "localhost"),
    "port": int(os.getenv("RABBITMQ_PORT", "5672")),
    "username": os.getenv("RABBITMQ_USER", "guest"),
    "password": os.getenv("RABBITMQ_PASSWD", "guest"),
    "use_tls": bool(int(os.getenv("RABBITMQ_USE_TLS", "0"))),
    "ca_cert": Path(ca_cert_path) if (ca_cert_path := os.getenv("RABBITMQ_CA_CERT_PATH", None)) is not None else None,
    "client_cert": Path(client_cert_path) if (client_cert_path := os.getenv("RABBITMQ_CLIENT_CERT_PATH", None)) is not None else None,
    "client_key": Path(client_key_path) if (client_key_path := os.getenv("RABBITMQ_CLIENT_KEY_PATH", None)) is not None else None,
    "prefetch_count": int(os.getenv("RABBITMQ_PREFETCH_COUNT", 10))
}

PUBLISHING_QUEUES: Dict[LiteralString, LiteralString] = {
    "payment_released": "payment.released",
    "payment_failed": "payment.failed",
}

LISTENING_QUEUES: Dict[LiteralString, LiteralString] = {
    "sagas_reserve": "payment.reserve",
    "sagas_release": "payment.release", 
    "request": "payment.request",
    "public_key": "client.public_key.payment",
}
PUBLIC_KEY: Dict[str, Optional[str]] = {"key": None}