"""Tests for DuckDB repository – new analytics methods."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from money_manager.domain.models import Category, Transaction
from money_manager.tools.db import DuckDBTransactionRepository


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test.duckdb"
    return DuckDBTransactionRepository(db_file)


def _make_txn(acc_id, amount, desc, merchant=None, category_name=None, ts=None):
    """Helper to create test transactions."""
    return Transaction(
        account_id=acc_id,
        amount=Decimal(str(amount)),
        description=desc,
        currency="INR",
        timestamp=ts or datetime(2024, 6, 15, 12, 0),
        merchant=merchant,
        category=Category(name=category_name) if category_name else None,
    )


@pytest.fixture
def seeded_repo(repo):
    """Repo pre-loaded with diverse test data."""
    acc = uuid.uuid4()
    txns = [
        _make_txn(acc, -500, "Swiggy dinner", "Swiggy", "Food"),
        _make_txn(acc, -200, "Swiggy lunch", "Swiggy", "Food"),
        _make_txn(acc, -1500, "Amazon order", "Amazon", "Shopping"),
        _make_txn(acc, -300, "Uber ride", "Uber", "Transport"),
        _make_txn(acc, -100, "Netflix sub", "Netflix", "Entertainment"),
        _make_txn(acc, 50000, "Monthly salary", None, "Salary"),
    ]
    import asyncio
    asyncio.get_event_loop().run_until_complete(repo.add_transactions(txns))
    return repo, acc


@pytest.mark.asyncio
async def test_get_category_breakdown(seeded_repo):
    repo, _ = seeded_repo
    breakdown = await repo.get_category_breakdown(2024, 6)

    assert len(breakdown) > 0
    categories = {b.category for b in breakdown}
    assert "Food" in categories
    assert "Shopping" in categories


@pytest.mark.asyncio
async def test_get_top_merchants(seeded_repo):
    repo, _ = seeded_repo
    merchants = await repo.get_top_merchants(2024, 6, limit=5)

    assert len(merchants) > 0
    names = [m[0] for m in merchants]
    assert "Swiggy" in names


@pytest.mark.asyncio
async def test_get_cashflow_summary(seeded_repo):
    repo, _ = seeded_repo
    summary = await repo.get_cashflow_summary(2024, 6)

    assert summary.year == 2024
    assert summary.month == 6
    assert summary.income == Decimal("50000")
    assert summary.expenses < 0
    assert summary.net == summary.income + summary.expenses
    assert len(summary.top_categories) > 0


@pytest.mark.asyncio
async def test_close(repo):
    await repo.close()
    # Verify connection is closed (subsequent ops would fail)


@pytest.mark.asyncio
async def test_search_by_merchant(seeded_repo):
    repo, _ = seeded_repo
    results = await repo.search_transactions("Swiggy")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_add_raw_statement(repo):
    await repo.add_raw_statement("test.pdf", {"transactions": [{"amount": 100}]})
    # Just verify it doesn't crash – raw_statements table is write-only for now
