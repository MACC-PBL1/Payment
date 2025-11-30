# -*- coding: utf-8 -*-
"""FastAPI router definitions."""
from ..messaging import (
    PUBLIC_KEY,
    RABBITMQ_CONFIG,
)
from ..sql import (
    ClientBalance,
    create_deposit_from_movement,
    Movement,
    Message,
)
from chassis.messaging import is_rabbitmq_healthy
from chassis.routers import (
    get_system_metrics,
    raise_and_log_error,
)
from chassis.security import create_jwt_verifier
from chassis.sql import get_db
from fastapi import (
    APIRouter, 
    Depends, 
    status
)
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import socket


logger = logging.getLogger(__name__)   

Router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)

# ------------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------------
@Router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    if not is_rabbitmq_healthy(RABBITMQ_CONFIG):
        raise_and_log_error(
            logger=logger,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            message="[LOG:REST] - RabbitMQ not reachable"
        )

    container_id = socket.gethostname()
    logger.debug(f"[LOG:REST] - GET '/health' served by {container_id}")
    return {
        "detail": f"OK - Served by {container_id}",
        "system_metrics": get_system_metrics()
    }

@Router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
    response_model=Message
)
async def health_check_auth(
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger))
):
    logger.debug("[LOG:REST] - GET '/health/auth' endpoint called.")

    user_id = token_data.get("sub")
    user_role = token_data.get("role")

    logger.info(f"[LOG:REST] - Valid JWT: user_id={user_id}, role={user_role}")

    return {
        "detail": f"Auth service is running. Authenticated as (id={user_id}, role={user_role})",
        "system_metrics": get_system_metrics()
    }


@Router.post(
    path="/deposit",
    response_model=ClientBalance,
    status_code=status.HTTP_201_CREATED,
    tags=["Deposit"]
)
async def create_deposit(
    amount: float,
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger)),
    db: AsyncSession = Depends(get_db)
):
    assert (client_id := token_data.get("sub")), "'sub' field should exist in the JWT."
    client_id = int(client_id)
  
    logger.debug(f"[LOG:REST] - POST '/deposit' called: client_id={client_id} amount={amount}")

    try:
        db_client_balance = await create_deposit_from_movement(
            db,
            Movement(client_id=client_id, amount=amount)
        )

        logger.info(f"[LOG:REST] - Deposit completed: client_id={client_id} amount={amount}",)
        return ClientBalance(
            client_id=db_client_balance.client_id,
            balance=db_client_balance.balance,
        )

    except Exception as e:
        raise_and_log_error(
            logger,
            status.HTTP_409_CONFLICT,
            f"[LOG:REST] - Error in making a deposit: {e}"
        )