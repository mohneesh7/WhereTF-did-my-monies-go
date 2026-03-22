"""Abstract contracts for infrastructure adapters – no concrete implementations here."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

import uuid
from datetime import datetime

from money_manager.domain.models import (
    CategoryBreakdown,
    MonthlySummary,
    Transaction,
)


# ── Repository Interface ──────────────────────────────────────────


class TransactionRepository(ABC):
    """Abstract contract for transaction persistence layer."""

    @abstractmethod
    async def add_transactions(self, transactions: List[Transaction]) -> None:
        """Persist a batch of transactions."""
        raise NotImplementedError

    @abstractmethod
    async def get_transactions(
        self,
        account_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Transaction]:
        """Fetch transactions with optional filters."""
        raise NotImplementedError

    @abstractmethod
    async def get_monthly_spend(self, year: int, month: int) -> Decimal:
        """Return total spend (negative sum) for a month."""
        raise NotImplementedError

    @abstractmethod
    async def search_transactions(self, query: str, limit: int = 50) -> List[Transaction]:
        """Text search over transaction descriptions/merchants."""
        raise NotImplementedError

    @abstractmethod
    async def get_category_breakdown(self, year: int, month: int) -> List[CategoryBreakdown]:
        """Return spend grouped by category for a month."""
        raise NotImplementedError

    @abstractmethod
    async def get_top_merchants(self, year: int, month: int, limit: int = 10) -> List[tuple[str, Decimal]]:
        """Return top merchants by spend for a month."""
        raise NotImplementedError

    @abstractmethod
    async def get_cashflow_summary(self, year: int, month: int) -> MonthlySummary:
        """Return income vs expenses summary for a month."""
        raise NotImplementedError

    @abstractmethod
    async def delete_all_transactions(self) -> int:
        """Delete every transaction. Return count of deleted rows."""
        raise NotImplementedError

    @abstractmethod
    async def delete_last_n_transactions(self, n: int) -> int:
        """Delete the last n transactions (by timestamp DESC). Return count deleted."""
        raise NotImplementedError

    async def close(self) -> None:
        """Clean up resources. Override if needed."""
        pass


# ── LLM Client Interface ─────────────────────────────────────────


class LLMClient(ABC):
    """Abstract contract for any LLM provider (OpenAI, Ollama, Gemini, etc)."""

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a chat completion."""
        raise NotImplementedError

    @abstractmethod
    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for vector search."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM backend is reachable."""
        raise NotImplementedError
