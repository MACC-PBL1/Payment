# -*- coding: utf-8 -*-
"""FastAPI router definitions."""
from ..sql import (
    ClientBalance,
    create_deposit_from_movement,
    Movement,
    Message,
)
from chassis.sql import get_db
from chassis.routers import raise_and_log_error
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

Router = APIRouter()

@Router.get(
    "/",
    summary="Health check endpoint",
    response_model=Message,
)
async def health_check():
    """Endpoint to check if everything started correctly."""
    logger.debug("GET '/' endpoint called.")
    return {
        "detail": "OK"
    }

@Router.post(
    path="/deposit",
    response_model=ClientBalance,
    status_code=status.HTTP_201_CREATED,
    tags=["Deposit"]
)
async def create_deposit(
    movement: Movement,
    db: AsyncSession = Depends(get_db)
):
    logger.debug("POST '/deposit' endpoint called")
    try:
        db_client_balance = await create_deposit_from_movement(db, movement)
        return ClientBalance(
            client_id=db_client_balance.client_id,
            balance=db_client_balance.balance,
        )
    except Exception as e:
        raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error in making a deposit: {e}")