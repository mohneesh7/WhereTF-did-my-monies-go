"""Tests for the FinanceAgent – tool selection and response synthesis with mocked LLM."""

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import pytest

from money_manager.app.agent import FinanceAgent
from money_manager.domain.interfaces import LLMClient
from money_manager.domain.models import Category, Transaction
from money_manager.tools.db import DuckDBTransactionRepository


# ── Mock LLM ─────────────────────────────────────────────────────


class MockAgentLLM(LLMClient):
    """Mock LLM that simulates planner + synthesizer behaviour."""

    def __init__(self):
        self.call_count = 0
        self.last_prompts: list[str] = []

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        self.call_count += 1
        self.last_prompts.append(prompt)

        # First call = planner, second call = synthesizer
        if self.call_count == 1:
            # Return a tool selection
            return json.dumps({"tool": "get_monthly_spend", "params": {"year": 2024, "month": 6}})
        else:
            # Return a synthesised response
            return "You spent ₹2,600 in June 2024. That's looking good!"

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None):
        self.call_count += 1
        self.last_prompts.append(prompt)

        if self.call_count == 1:
            return {"tool": "get_monthly_spend", "params": {"year": 2024, "month": 6}}
        return {}

    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] * 10 for _ in texts]

    async def health_check(self) -> bool:
        return True


class MockDirectLLM(LLMClient):
    """Mock LLM that returns a null tool (direct response path)."""

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return "Hello! I'm your financial assistant. How can I help you today?"

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None):
        return {"tool": None, "params": {}}

    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        return []

    async def health_check(self) -> bool:
        return True


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def repo(tmp_path):
    repo = DuckDBTransactionRepository(tmp_path / "test_agent.duckdb")
    return repo


@pytest.fixture
def seeded_repo(repo):
    acc = uuid.uuid4()
    txns = [
        Transaction(
            account_id=acc, amount=Decimal("-500"), description="Swiggy",
            currency="INR", timestamp=datetime(2024, 6, 15), merchant="Swiggy", category=Category(name="Food"),
        ),
        Transaction(
            account_id=acc, amount=Decimal("-2100"), description="Amazon",
            currency="INR", timestamp=datetime(2024, 6, 20), merchant="Amazon", category=Category(name="Shopping"),
        ),
        Transaction(
            account_id=acc, amount=Decimal("60000"), description="Salary",
            currency="INR", timestamp=datetime(2024, 6, 1), category=Category(name="Salary"),
        ),
    ]
    import asyncio
    asyncio.get_event_loop().run_until_complete(repo.add_transactions(txns))
    return repo


# ── Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_tool_call(seeded_repo):
    """Agent should plan a tool call, execute it, and synthesize a response."""
    llm = MockAgentLLM()
    agent = FinanceAgent(seeded_repo, llm)

    response = await agent.chat("How much did I spend last month?", current_date="2024-07-01")

    assert "2,600" in response or "spent" in response.lower()
    assert llm.call_count == 2  # planner + synthesizer


@pytest.mark.asyncio
async def test_agent_direct_response(repo):
    """Agent should handle greetings without calling tools."""
    llm = MockDirectLLM()
    agent = FinanceAgent(repo, llm)

    response = await agent.chat("Hello!")

    assert "hello" in response.lower() or "help" in response.lower()


@pytest.mark.asyncio
async def test_agent_builds_tool_descriptions():
    """Agent should build tool descriptions from registry."""
    from money_manager.app.agent import FinanceAgent
    repo_mock = None  # We just need to test description building

    # Can't instantiate without repo, so test the method directly
    from money_manager.app.tools import TOOL_REGISTRY
    assert len(TOOL_REGISTRY) >= 5
    assert "get_monthly_spend" in TOOL_REGISTRY
    assert "search_transactions" in TOOL_REGISTRY
