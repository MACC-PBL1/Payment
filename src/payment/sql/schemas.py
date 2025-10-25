# -*- coding: utf-8 -*-
"""Classes for Request/Response schema definitions."""
from typing import Optional
from pydantic import BaseModel, Field

class ClientBalance(BaseModel):
    """Client balance schema"""
    client_id: int = Field(examples=[234])
    balance: float = Field(examples=[10.1])

class Message(BaseModel):
    """Message schema definition."""
    detail: Optional[str] = Field(examples=None)

class Movement(BaseModel):
    """Money movement petition"""
    client_id: int = Field(examples=[1])
    amount: float = Field(examples=[0.0])