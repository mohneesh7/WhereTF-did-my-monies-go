"""Tests for deterministic analytics tools."""

import json
import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from money_manager.app.tools import (
    get_cashflow_summary,
    get_category_breakdown,
    get_monthly_spend,
    get_top_merchants,
    search_transactions,
)
from money_manager.domain.models import Category, Transaction
from money_manager.tools.db import DuckDBTransactionRepository


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_tools.duckdb"
    return DuckDBTransactionRepository(db_file)


@pytest.fixture
def seeded_repo(repo):
    acc = uuid.uuid4()
    txns = [
        Transaction(
            account_id=acc, amount=Decimal("-800"), description="Groceries",
            currency="INR", timestamp=datetime(2024, 3, 10), merchant="BigBasket", category=Category(name="Groceries"),
        ),
        Transaction(
            account_id=acc, amount=Decimal("-200"), description="Auto ride",
            currency="INR", timestamp=datetime(2024, 3, 15), merchant="Ola", category=Category(name="Transport"),
        ),
        Transaction(
            account_id=acc, amount=Decimal("60000"), description="Salary",
            currency="INR", timestamp=datetime(2024, 3, 1), merchant=None, category=Category(name="Salary"),
        ),
    ]
    import asyncio
    asyncio.get_event_loop().run_until_complete(repo.add_transactions(txns))
    return repo


@pytest.mark.asyncio
async def test_get_monthly_spend(seeded_repo):
    result = await get_monthly_spend(seeded_repo, 2024, 3)
    data = json.loads(result)
    assert data["total_spend"] == -1000.0


@pytest.mark.asyncio
async def test_search_transactions(seeded_repo):
    result = await search_transactions(seeded_repo, "Groceries")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["description"] == "Groceries"


@pytest.mark.asyncio
async def test_get_category_breakdown(seeded_repo):
    result = await get_category_breakdown(seeded_repo, 2024, 3)
    data = json.loads(result)
    assert len(data) == 2  # Groceries + Transport (Salary is positive)
    cats = {d["category"] for d in data}
    assert "Groceries" in cats


@pytest.mark.asyncio
async def test_get_top_merchants(seeded_repo):
    result = await get_top_merchants(seeded_repo, 2024, 3)
    data = json.loads(result)
    assert len(data) == 2  # BigBasket + Ola


@pytest.mark.asyncio
async def test_get_cashflow_summary(seeded_repo):
    result = await get_cashflow_summary(seeded_repo, 2024, 3)
    data = json.loads(result)
    assert data["income"] == 60000.0
    assert data["expenses"] == -1000.0
    assert data["net"] == 59000.0
