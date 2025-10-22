# -*- coding: utf-8 -*-
"""Functions that interact with the database."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from . import models, schemas

logger = logging.getLogger(__name__)

async def create_deposit_from_movement(
    db: AsyncSession,
    movement: schemas.Movement,
) -> models.ClientBalance:
    db_client_balance = await db.get(models.ClientBalance, movement.client_id)
    if db_client_balance is not None:
        db_client_balance.balance += movement.amount
    else:
        db_client_balance = models.ClientBalance()
        db_client_balance.client_id = movement.client_id
        db_client_balance.balance = movement.amount
        db.add(db_client_balance)
    return db_client_balance

async def try_create_payment(
    db: AsyncSession,
    movement: schemas.Movement,
) -> models.ClientBalance:
    db_client_balance = await db.get(models.ClientBalance, movement.client_id)
    assert db_client_balance is not None, "In order to pay, the client must exist."
    result = db_client_balance.balance - movement.amount
    if result < 0:
        raise RuntimeError("Not enough balance in the account")
    db_client_balance.balance = result
    return db_client_balance
