# -*- coding: utf-8 -*-
"""Main file to start FastAPI application."""
from contextlib import asynccontextmanager
from threading import Thread
from typing import (
    Dict,
    List, 
    LiteralString,
    Union
)
import logging.config
import asyncio
import os

from fastapi import (
    FastAPI, 
    Depends,
)
from hypercorn.asyncio import serve
from hypercorn.config import Config

from .dependencies import get_db
from .messaging import (
    types as mes_types,
    register_queue_handler,
    start_rabbitmq_listener,
    publisher
)
from .routers import main_router
from .sql import (
    crud, 
    database, 
    models,
    schemas,
)

# Configure logging ################################################################################
logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)

# RabbitMQ Configuration ###########################################################################
PUBLIC_KEY = "" # Por ahora asi que no se bien como va

# RabbitMQ Configuration ###########################################################################
LISTENING_QUEUES: List[LiteralString] = [
    "client.public_key",
    "payment.request",
]
WRITING_QUEUES: List[LiteralString] = [
    "client.refresh_public_key",
    "payment.confirmation",
]
RABBITMQ_CONFIG = {
    "host": "rabbitmq",
    "port": 5672,
    "username": "guest",
    "password": "guest",
    "use_tls": False,
    "prefetch_count": 10,
    # For TLS in production:
    # "host": "rabbitmq.example.com",
    # "port": 5671,
    # "use_tls": True,
    # "ca_cert": Path("/path/to/ca_certificate.pem"),
    # "client_cert": Path("/path/to/client_certificate.pem"),
    # "client_key": Path("/path/to/client_key.pem"),
}
LISTENER_THREADS: List[Thread] = []

@register_queue_handler(LISTENING_QUEUES[0])
def request(message: mes_types.MessageType) -> None:
    assert (client_id := message.get("client_id")) is not None, "'client_id' field should exist."
    assert (order_id := message.get("order_id")) is not None, "'order_id' field should exist."
    assert (amount := message.get("amount")) is not None, "'amount' field should exist."

    client_id = int(client_id)
    order_id = int(order_id)
    amount = float(amount)

    response: Dict[str, Union[int, str]] = {
        "client_id": client_id,
        "order_id": order_id,
    }
    
    try:
        _ = asyncio.run(crud.try_create_payment(Depends(get_db), schemas.Movement(client_id=client_id, amount=order_id)))
        response["status"] = "OK"
    except Exception as e:
        response["status"] = f"Error: {e}"

    with publisher.RabbitMQPublisher(
        host=RABBITMQ_CONFIG["host"],
        port=RABBITMQ_CONFIG["port"],
        username=RABBITMQ_CONFIG["username"],
        password=RABBITMQ_CONFIG["password"],
        queue="payment.confirmation",
        use_tls=False,
    ) as publi:
        publi.publish(message=response)


@register_queue_handler(LISTENING_QUEUES[1])
def public_key_update(message: mes_types.MessageType) -> None:
    global PUBLIC_KEY
    assert (public_key := message.get("public_key")) is not None, "'public_key' field should exist."
    PUBLIC_KEY = str(public_key)


# App Lifespan #####################################################################################
@asynccontextmanager
async def lifespan(__app: FastAPI):
    """Lifespan context manager."""
    global LISTENER_THREADS

    try:
        logger.info("Starting up")
        try:
            logger.info("Creating database tables")
            async with database.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)
        except Exception as e:
            logger.error(
                f"Could not create tables at startup: {e}",
            )
        
        logger.info("Starting RabbitMQ listeners")        
        try:
            for listen_queue in LISTENING_QUEUES:
                LISTENER_THREADS.append(
                    Thread(
                        target=start_rabbitmq_listener,
                        args=(listen_queue, RABBITMQ_CONFIG),
                        daemon=True,
                    )
                )
            for thread in LISTENER_THREADS:
                thread.start()
        except Exception as e:
            logger.error(
                f"Could not start the RabbitMQ listeners: {e}"
            )
        yield
    finally:
        logger.info("Shutting down database")
        await database.engine.dispose()

# OpenAPI Documentation ############################################################################
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
logger.info("Running app version %s", APP_VERSION)
DESCRIPTION = """
Payment processing application.
"""

APP = FastAPI(
    redoc_url=None,  # disable redoc documentation.
    title="FastAPI - Payment",
    description=DESCRIPTION,
    version=APP_VERSION,
    servers=[{"url": "/", "description": "Development"}],
    license_info={
        "name": "MIT License",
        "url": "https://choosealicense.com/licenses/mit/",
    },
    openapi_tags=[
        {
            "name": "Payment",
            "description": "Endpoints related to payment",
        },
    ],
    lifespan=lifespan,
)

APP.include_router(main_router.router)

def start_server():
    ## Run here
    config = Config()

    config.bind = [os.getenv("HOST", "0.0.0.0") + ":" + os.getenv("PORT", "8000")]
    config.workers = int(os.getenv("WORKERS", "1"))

    logger.info("Starting Hypercorn server on %s", config.bind)

    asyncio.run(serve(APP, config)) # type: ignore