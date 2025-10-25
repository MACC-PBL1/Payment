# -*- coding: utf-8 -*-
"""Database models definitions. Table representations as class."""
from chassis.sql import BaseModel
from sqlalchemy import (
    Float,
    Integer, 
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

class ClientBalance(BaseModel):
    __tablename__ = "client_balance"
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)