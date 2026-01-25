from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class AccountType(str,Enum):
    CASH = "CASH"
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    LOAN = "LOAN"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"

class CurrencyType(str,Enum):
    INR = "INR"
    USD = "USD"

class Category(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    parent_id: Optional[uuid.UUID] = None
    name: str
    description: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

class Account(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    currency: CurrencyType = CurrencyType.INR
    type: AccountType
    metadata: Optional[dict[str, Any]] = None

class Transaction(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    account_id: uuid.UUID
    account: Optional[Account] = None
    category: Optional[Category] = None
    amount: Decimal
    description: str
    currency: CurrencyType = CurrencyType.INR
    timestamp: datetime
    merchant: Optional[str] = None
    raw_metadata: Optional[dict[str, Any]] = None
