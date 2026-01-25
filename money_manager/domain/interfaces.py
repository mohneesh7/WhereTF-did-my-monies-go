from abc import ABC, abstractmethod
from typing import List, Optional, Protocol
import uuid
from datetime import datetime
from decimal import Decimal

from money_manager.domain.models import Transaction


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


class LLMClient(ABC):
    """Abstract contract for any LLM provider (OpenAI, local, etc)."""

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a chat completion."""
        raise NotImplementedError

    @abstractmethod
    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for vector DB."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if LLM backend is reachable."""
        raise NotImplementedError
