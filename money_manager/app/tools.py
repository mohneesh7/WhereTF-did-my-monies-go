"""Deterministic analytics tools – wrappers around the repository for agent use.

The LLM agent calls these tools instead of writing raw SQL.
Each tool is registered in TOOL_REGISTRY with metadata the LLM uses to decide which tool to invoke.
"""

import json
from decimal import Decimal

from money_manager.domain.interfaces import TransactionRepository


# ── Helper ───────────────────────────────────────────────────────

def _decimal_default(obj):
    """JSON serializer for Decimal."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _format_json(data) -> str:
    """Pretty-print data to JSON string."""
    return json.dumps(data, indent=2, default=_decimal_default)


# ── Tool Functions ───────────────────────────────────────────────


async def get_monthly_spend(repo: TransactionRepository, year: int, month: int) -> str:
    """Get total spending for a given month."""
    spend = await repo.get_monthly_spend(year, month)
    return _format_json({
        "year": year,
        "month": month,
        "total_spend": spend,
        "currency": "INR",
    })


async def search_transactions(repo: TransactionRepository, query: str, limit: int = 20) -> str:
    """Search transactions by description or merchant."""
    txns = await repo.search_transactions(query, limit)
    return _format_json([
        {
            "date": t.timestamp.strftime("%Y-%m-%d"),
            "description": t.description,
            "amount": t.amount,
            "merchant": t.merchant,
            "category": t.category.name if t.category else None,
        }
        for t in txns
    ])


async def get_category_breakdown(repo: TransactionRepository, year: int, month: int) -> str:
    """Get spending breakdown by category for a month."""
    breakdown = await repo.get_category_breakdown(year, month)
    return _format_json([
        {
            "category": b.category,
            "total_amount": b.total_amount,
            "transaction_count": b.transaction_count,
        }
        for b in breakdown
    ])


async def get_top_merchants(repo: TransactionRepository, year: int, month: int, limit: int = 10) -> str:
    """Get top merchants by spend for a month."""
    merchants = await repo.get_top_merchants(year, month, limit)
    return _format_json([
        {"merchant": name, "total_spend": amount}
        for name, amount in merchants
    ])


async def get_cashflow_summary(repo: TransactionRepository, year: int, month: int) -> str:
    """Get income vs expenses summary for a month."""
    summary = await repo.get_cashflow_summary(year, month)
    return _format_json({
        "year": summary.year,
        "month": summary.month,
        "income": summary.income,
        "expenses": summary.expenses,
        "net": summary.net,
        "top_categories": [
            {"category": c.category, "amount": c.total_amount, "count": c.transaction_count}
            for c in summary.top_categories
        ],
    })


# ── Tool Registry ────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "get_monthly_spend": {
        "function": get_monthly_spend,
        "description": "Get total spending for a given month. Use when the user asks about monthly spend or expenses.",
        "parameters": {
            "year": {"type": "int", "description": "The year (e.g. 2024)"},
            "month": {"type": "int", "description": "The month (1-12)"},
        },
    },
    "search_transactions": {
        "function": search_transactions,
        "description": "Search transactions by keyword in description or merchant name. Use when the user asks to find specific transactions.",
        "parameters": {
            "query": {"type": "str", "description": "Search keyword"},
            "limit": {"type": "int", "description": "Max results (default 20)", "optional": True},
        },
    },
    "get_category_breakdown": {
        "function": get_category_breakdown,
        "description": "Get spending breakdown by category for a month. Use when the user asks about spending categories or where their money goes.",
        "parameters": {
            "year": {"type": "int", "description": "The year"},
            "month": {"type": "int", "description": "The month (1-12)"},
        },
    },
    "get_top_merchants": {
        "function": get_top_merchants,
        "description": "Get the top merchants by total spend for a month. Use when the user asks about which merchants/shops they spend most at.",
        "parameters": {
            "year": {"type": "int", "description": "The year"},
            "month": {"type": "int", "description": "The month (1-12)"},
            "limit": {"type": "int", "description": "Number of merchants (default 10)", "optional": True},
        },
    },
    "get_cashflow_summary": {
        "function": get_cashflow_summary,
        "description": "Get income vs expenses summary for a month. Use when the user asks about cashflow, savings, or income/expense overview.",
        "parameters": {
            "year": {"type": "int", "description": "The year"},
            "month": {"type": "int", "description": "The month (1-12)"},
        },
    },
}
