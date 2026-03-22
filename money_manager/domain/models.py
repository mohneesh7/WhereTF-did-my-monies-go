"""Domain models – pure data, no infrastructure dependencies."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import uuid
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class AccountType(str, Enum):
    CASH = "CASH"
    BANK = "BANK"
    CREDIT_CARD = "CREDIT_CARD"
    DEBIT_CARD = "DEBIT_CARD"
    LOAN = "LOAN"
    INVESTMENT = "INVESTMENT"
    OTHER = "OTHER"


class CurrencyType(str, Enum):
    INR = "INR"
    USD = "USD"


# ── Core Domain Models ───────────────────────────────────────────


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


# ── Analytics Response Models ────────────────────────────────────


class CategoryBreakdown(BaseModel):
    """Spend breakdown for a single category."""

    category: str
    total_amount: Decimal
    transaction_count: int


class MonthlySummary(BaseModel):
    """Income vs expenses summary for a month."""

    year: int
    month: int
    income: Decimal
    expenses: Decimal
    net: Decimal
    top_categories: list[CategoryBreakdown] = Field(default_factory=list)


class RawStatement(BaseModel):
    """Persisted raw bank statement before normalization."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: str
    raw_json: dict[str, Any]
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class IngestionResult(BaseModel):
    """Result of the ingestion pipeline."""

    source: str
    total_extracted: int
    valid_count: int
    rejected_count: int
    rejected_rows: list[dict[str, Any]] = Field(default_factory=list)
