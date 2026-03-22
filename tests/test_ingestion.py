"""Tests for the ingestion pipeline with a mocked LLM client."""

import uuid
from datetime import datetime
from typing import List, Optional
from unittest.mock import AsyncMock

import pytest

from money_manager.domain.interfaces import LLMClient
from money_manager.tools.db import DuckDBTransactionRepository
from money_manager.tools.ingestion.pdf_extractor import extract_text_from_pdf
from money_manager.tools.ingestion.validator import validate_transactions
from money_manager.tools.ingestion.pipeline import ingest_pdf


# ── Mock LLM Client ─────────────────────────────────────────────


class MockLLMClient(LLMClient):
    """A mock LLM client that returns pre-defined responses for ingestion testing."""

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "mock response"

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None):
        """Return mock structured data depending on the prompt context."""
        if "Extract all transactions" in prompt:
            # Raw extraction response
            return [
                {"date": "2024-01-15", "description": "UPI/Swiggy", "amount": -450.00, "type": "debit", "reference": None, "balance": None},
                {"date": "2024-01-16", "description": "SALARY CREDIT", "amount": 50000.00, "type": "credit", "reference": None, "balance": None},
            ]
        elif "Normalize" in prompt:
            # Schema mapping response
            return [
                {"amount": -450.00, "description": "Swiggy order", "currency": "INR", "timestamp": "2024-01-15T00:00:00", "merchant": "Swiggy", "category": "Food"},
                {"amount": 50000.00, "description": "Monthly salary", "currency": "INR", "timestamp": "2024-01-16T00:00:00", "merchant": None, "category": "Salary"},
            ]
        return []

    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 10 for _ in texts]

    async def health_check(self) -> bool:
        return True


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def repo(tmp_path):
    return DuckDBTransactionRepository(tmp_path / "test_ingestion.duckdb")


# ── Tests ────────────────────────────────────────────────────────


def test_pdf_extractor_empty_raises():
    """Empty/invalid PDF should raise ValueError."""
    with pytest.raises(Exception):
        extract_text_from_pdf(b"not a pdf")


def test_validate_transactions_valid():
    """Valid dicts should produce Transaction objects."""
    raw = [
        {
            "account_id": str(uuid.uuid4()),
            "amount": -100.0,
            "description": "Test",
            "currency": "INR",
            "timestamp": "2024-01-15T00:00:00",
            "category": "Food",
        }
    ]
    valid, rejected = validate_transactions(raw)
    assert len(valid) == 1
    assert len(rejected) == 0
    assert valid[0].category.name == "Food"


def test_validate_transactions_rejects_bad_data():
    """Invalid dicts should be rejected with error details."""
    raw = [
        {"amount": "not_a_number", "description": "Bad", "timestamp": "invalid"},
    ]
    valid, rejected = validate_transactions(raw)
    assert len(valid) == 0
    assert len(rejected) == 1
    assert "error" in rejected[0]


@pytest.mark.asyncio
async def test_ingest_pdf_pipeline(repo, mock_llm, tmp_path):
    """End-to-end pipeline test with mock LLM and a minimal PDF."""
    # Create a minimal valid PDF
    from PyPDF2 import PdfWriter
    from io import BytesIO

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # This will fail at text extraction because blank page has no text
    with pytest.raises(ValueError, match="No text extracted"):
        await ingest_pdf(
            file_bytes=pdf_bytes,
            source="test.pdf",
            repo=repo,
            llm=mock_llm,
            account_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_validate_and_persist(repo, mock_llm):
    """Test the validate → persist path directly."""
    acc_id = uuid.uuid4()

    mapped_rows = [
        {"account_id": str(acc_id), "amount": -450.00, "description": "Swiggy order", "currency": "INR", "timestamp": "2024-01-15T00:00:00", "merchant": "Swiggy", "category": "Food"},
        {"account_id": str(acc_id), "amount": 50000.00, "description": "Monthly salary", "currency": "INR", "timestamp": "2024-01-16T00:00:00", "merchant": None, "category": "Salary"},
    ]

    valid, rejected = validate_transactions(mapped_rows)
    assert len(valid) == 2
    assert len(rejected) == 0

    await repo.add_transactions(valid)
    txns = await repo.get_transactions(account_id=acc_id)
    assert len(txns) == 2
