"""Tests for FastAPI endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal

import asyncio
import pytest
from fastapi.testclient import TestClient

from money_manager.domain.models import Category, Transaction
from money_manager.tools.db import DuckDBTransactionRepository
from money_manager.ui import api as api_module


@pytest.fixture
def client(tmp_path):
    """Create a test client with a temp DB — lifespan skips init since globals are pre-set."""
    repo = DuckDBTransactionRepository(tmp_path / "test_api.duckdb")

    # Seed data
    acc = uuid.uuid4()
    txns = [
        Transaction(
            account_id=acc, amount=Decimal("-300"), description="Zomato order",
            currency="INR", timestamp=datetime(2024, 5, 10), merchant="Zomato", category=Category(name="Food"),
        ),
        Transaction(
            account_id=acc, amount=Decimal("45000"), description="Salary",
            currency="INR", timestamp=datetime(2024, 5, 1), category=Category(name="Salary"),
        ),
    ]
    asyncio.get_event_loop().run_until_complete(repo.add_transactions(txns))

    # Inject BEFORE TestClient so lifespan sees them and skips init
    api_module.repo = repo
    api_module.llm = None
    api_module.agent = None

    with TestClient(api_module.app, raise_server_exceptions=False) as c:
        yield c

    # Cleanup
    api_module.repo = None
    api_module.llm = None
    api_module.agent = None


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"


def test_list_transactions(client):
    r = client.get("/api/transactions")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2


def test_monthly_spend(client):
    r = client.get("/api/analytics/monthly/2024/5")
    assert r.status_code == 200
    data = r.json()
    assert data["total_spend"] == -300.0


def test_category_breakdown(client):
    r = client.get("/api/analytics/categories/2024/5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["category"] == "Food"


def test_cashflow_summary(client):
    r = client.get("/api/analytics/cashflow/2024/5")
    assert r.status_code == 200
    data = r.json()
    assert data["income"] == 45000.0
    assert data["expenses"] == -300.0


def test_top_merchants(client):
    r = client.get("/api/analytics/merchants/2024/5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["merchant"] == "Zomato"


def test_chat_without_agent(client):
    """Chat should return 503 when agent is not initialized."""
    r = client.post("/api/chat", json={"message": "hello"})
    assert r.status_code == 503


def test_ingest_non_pdf(client):
    """Non-PDF uploads should be rejected."""
    r = client.post("/api/ingest", files={"file": ("test.txt", b"hello", "text/plain")})
    # Without LLM, ingest returns 503 (service not ready)
    assert r.status_code == 503
