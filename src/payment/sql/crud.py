# -*- coding: utf-8 -*-
"""Functions that interact with the database."""
from .models import ClientBalance
from .schemas import Movement
from chassis.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

async def create_deposit_from_movement(
    db: AsyncSession,
    movement: Movement,
) -> ClientBalance:
    db_client_balance = await db.get(ClientBalance, movement.client_id)
    if db_client_balance is not None:
        db_client_balance.balance += movement.amount
    else:
        db_client_balance = ClientBalance()
        db_client_balance.client_id = movement.client_id
        db_client_balance.balance = movement.amount
        db.add(db_client_balance)
    return db_client_balance

async def try_create_payment(
    db: AsyncSession,
    movement: Movement,
) -> ClientBalance:
    db_client_balance = await db.get(ClientBalance, movement.client_id)
    assert db_client_balance is not None, "In order to pay, the client must have a wallet."
    result = db_client_balance.balance - movement.amount
    if result < 0:
        raise ValueError("Not enough balance in the account")
    db_client_balance.balance = result
    return db_client_balance
