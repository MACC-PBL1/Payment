# -*- coding: utf-8 -*-
"""FastAPI router definitions."""
from ..messaging import PUBLIC_KEY
from ..sql import (
    ClientBalance,
    create_deposit_from_movement,
    Movement,
    Message,
)
from chassis.sql import get_db
from chassis.security import create_jwt_verifier
from chassis.routers import raise_and_log_error
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging


from chassis.logging.rabbitmq_logging import log_with_context   

logger = logging.getLogger("payment")   

Router = APIRouter(
    prefix="/payment",
    tags=["Payment"]
)

@Router.get(
    "/health",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    """Endpoint to check if everything started correctly."""
    logger.debug("GET '/payment/health' endpoint called.")
    return {
        "detail": "OK"
    }

@Router.get(
    "/health/auth",
    summary="Health check endpoint (JWT protected)",
)
async def health_check_auth(
    token_data: dict = Depends(create_jwt_verifier(lambda: PUBLIC_KEY["key"], logger))
):
    logger.debug("GET '/payment/auth' called.")

    user_id = token_data.get("sub")
    user_email = token_data.get("email")
    user_role = token_data.get("role")

    logger.info(f"Valid JWT → user_id={user_id}, email={user_email}, role={user_role}")

    logger.info("Authenticated health check", extra={"client_id": user_id})


    return {
        "detail": f"Payment service is running. Authenticated as {user_email} (id={user_id}, role={user_role})"
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
    logger.debug(f"POST '/deposit' called (amount={amount})")

    assert (client_id := token_data.get("sub")), "'sub' field should exist in the JWT."
    client_id = int(client_id)

 
    logger.debug(
        "Deposit request received",
        extra={"client_id": client_id}
    )


    try:
        db_client_balance = await create_deposit_from_movement(
            db,
            Movement(client_id=client_id, amount=amount)
        )

        logger.info(
            f"Deposit completed (amount={amount})",
        extra={"client_id": client_id}
        )


        return ClientBalance(
            client_id=db_client_balance.client_id,
            balance=db_client_balance.balance,
        )

    except Exception as e:
        # This function already logs and raises HTTPException
        raise_and_log_error(
            logger,
            status.HTTP_409_CONFLICT,
            f"Error in making a deposit: {e}"
        )