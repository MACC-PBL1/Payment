# -*- coding: utf-8 -*-
"""Main file to start FastAPI application."""
from .messaging import (
    LISTENING_QUEUES,
    RABBITMQ_CONFIG,
)
from .routers import Router
from chassis.consul import ConsulClient 
from chassis.messaging import (
    start_rabbitmq_listener
)
from chassis.sql import (
    Base,
    Engine,
)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config
from threading import Thread
from typing import List
import asyncio
import logging.config
import os

# Configure logging ################################################################################
from chassis.logging.rabbitmq_logging import setup_rabbitmq_logging

logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)
setup_rabbitmq_logging("payment", RABBITMQ_CONFIG, level=logging.INFO)


from .messaging import LISTENING_QUEUES
from .routers import Router

# RabbitMQ Configuration ###########################################################################

LISTENER_THREADS: List[Thread] = []


# App Lifespan #####################################################################################
@asynccontextmanager
async def lifespan(__app: FastAPI):
    """Lifespan context manager."""
    try:
        logger.info("[LOG:PAYMENT] - Starting up")
        try:
            logger.info("[LOG:PAYMENT] - Creating database tables")
            async with Engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("[LOG:PAYMENT] - Starting RabbitMQ listeners")
            try:
                for _, queue in LISTENING_QUEUES.items():
                    Thread(
                        target=start_rabbitmq_listener,
                        args=(queue, RABBITMQ_CONFIG),
                        daemon=True,
                    ).start()
            except Exception as e:
                logger.error(
                    f"[LOG:PAYMENT] - Could not start the RabbitMQ listeners: Reason={e}",
                    exc_info=True,
                )
            logger.info("[LOG:PAYMENT] - Registering service to Consul...")
            try:
                service_port = int(os.getenv("PORT", "8000"))
                consul = ConsulClient(logger=logger)
                consul.register_service(service_name="payment-service", port=service_port, health_path="/payment/health")
            except Exception as e:
                logger.error(f"[LOG:PAYMENT] - Failed to register with Consul: {e}", exc_info=True)
        except Exception:
            logger.error(
                "[LOG:PAYMENT] - Could not create tables at startup",
                exc_info=True,
            )
        yield
    finally:
        logger.info("[LOG:PAYMENT] - Shutting down database")
        await Engine.dispose()

# OpenAPI Documentation ############################################################################
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
logger.info("[LOG:PAYMENT] - Running app version %s", APP_VERSION)
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

APP.include_router(Router)

def start_server():
    ## Run here
    config = Config()

    config.bind = [os.getenv("HOST", "0.0.0.0") + ":" + os.getenv("PORT", "8000")]
    config.workers = int(os.getenv("WORKERS", "1"))

    logger.info("[LOG:PAYMENT] - Starting Hypercorn server on %s", config.bind)

    asyncio.run(serve(APP, config)) # type: ignore