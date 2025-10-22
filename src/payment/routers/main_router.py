# -*- coding: utf-8 -*-
"""FastAPI router definitions."""
import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..dependencies import get_db
from ..sql import (
    crud,
    schemas
)
from .router_utils import raise_and_log_error

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get(
    "/",
    summary="Health check endpoint",
    response_model=schemas.Message,
)
async def health_check():
    """Endpoint to check if everything started correctly."""
    logger.debug("GET '/' endpoint called.")
    return {
        "detail": "OK"
    }

@router.post(
    path="/deposit",
    response_model=schemas.ClientBalance,
    status_code=status.HTTP_201_CREATED,
    tags=["Deposit"]
)
async def create_deposit(
    movement: schemas.Movement,
    db: AsyncSession = Depends(get_db)
):
    logger.debug("POST '/deposit' endpoint called")
    try:
        db_client_balance = await crud.create_deposit_from_movement(db, movement)
        return schemas.ClientBalance(
            client_id=db_client_balance.client_id, # type: ignore
            balance=db_client_balance.balance, # type: ignore
        )
    except Exception as e:
        raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error in making a deposit: {e}")

# @router.post(
#     path="/payment",
#     response_model=schemas.ClientBalance,
#     status_code=status.HTTP_201_CREATED,
#     tags=["Payment"]
# )
# async def create_payment(
#     movement: schemas.Movement,
#     db: AsyncSession = Depends(get_db)
# ):
#     logger.debug("POST '/payment' endpoint called")
#     try:
#         db_client_balance = await crud.try_create_payment(db, movement)
#         return schemas.ClientBalance(
#             client_id=db_client_balance.client_id, # type: ignore
#             balance=db_client_balance.balance # type: ignore
#         )
#     except Exception as e:
#         raise_and_log_error(logger, status.HTTP_409_CONFLICT, f"Error in making payment: {e}")