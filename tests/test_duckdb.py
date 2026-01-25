import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from money_manager.tools.db import DuckDBTransactionRepository
from money_manager.domain.models import Transaction, Category


@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test.duckdb"
    return DuckDBTransactionRepository(db_file)


@pytest.mark.asyncio
async def test_add_and_get_transactions(repo):
    acc_id = uuid.uuid4()
    txn = Transaction(
        account_id=acc_id,
        amount=Decimal("-100.50"),
        description="Swiggy order",
        currency="INR",
        timestamp=datetime.utcnow(),
        merchant="Swiggy",
        category=Category(name="Food"),
    )

    await repo.add_transactions([txn])
    txns = await repo.get_transactions(account_id=acc_id)

    assert len(txns) == 1
    assert txns[0].amount == Decimal("-100.50")


@pytest.mark.asyncio
async def test_monthly_spend(repo):
    acc_id = uuid.uuid4()
    now = datetime.utcnow()

    txns = [
        Transaction(account_id=acc_id, amount=Decimal("-100"), description="A", currency="INR", timestamp=now),
        Transaction(account_id=acc_id, amount=Decimal("-200"), description="B", currency="INR", timestamp=now),
        Transaction(account_id=acc_id, amount=Decimal("500"), description="Salary", currency="INR", timestamp=now),
    ]

    await repo.add_transactions(txns)

    spend = await repo.get_monthly_spend(now.year, now.month)
    assert spend == Decimal("-300")


@pytest.mark.asyncio
async def test_search(repo):
    acc_id = uuid.uuid4()
    txn = Transaction(
        account_id=acc_id,
        amount=Decimal("-50"),
        description="Uber ride",
        currency="INR",
        timestamp=datetime.utcnow(),
    )

    await repo.add_transactions([txn])
    results = await repo.search_transactions("Uber")

    assert len(results) == 1
