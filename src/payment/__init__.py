# -*- coding: utf-8 -*-
"""Main file to start FastAPI application."""
from contextlib import asynccontextmanager
import logging.config
import asyncio
import os

from fastapi import FastAPI
from hypercorn.asyncio import serve
from hypercorn.config import Config

from .routers import main_router
from .sql import models
from .sql import database

# Configure logging ################################################################################
logging.config.fileConfig(os.path.join(os.path.dirname(__file__), "logging.ini"))
logger = logging.getLogger(__name__)


# App Lifespan #####################################################################################
@asynccontextmanager
async def lifespan(__app: FastAPI):
    """Lifespan context manager."""
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

    asyncio.run(serve(APP, config))