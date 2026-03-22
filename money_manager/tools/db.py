"""DuckDB implementation of the TransactionRepository interface."""

import asyncio
import json
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import List, Optional

import duckdb
from pydantic import BaseModel

from money_manager.domain.interfaces import TransactionRepository
from money_manager.domain.models import (
    Category,
    CategoryBreakdown,
    MonthlySummary,
    Transaction,
)

DB_PATH = Path("money.duckdb")


class _DomainEncoder(json.JSONEncoder):
    """Handle Pydantic models, UUIDs, Decimals, datetimes, and Enums."""

    def default(self, obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class DuckDBTransactionRepository(TransactionRepository):
    """Async-wrapped DuckDB repository for transactions and raw statements."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self.conn = duckdb.connect(self.db_path)
        self._init_tables()

    # ── Table Initialisation ─────────────────────────────────────

    def _init_tables(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS raw_statements (
            id TEXT PRIMARY KEY,
            source TEXT,
            raw_json JSON,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            category TEXT,
            amount DECIMAL(18,2),
            currency TEXT,
            description TEXT,
            timestamp TIMESTAMP,
            merchant TEXT
        );
        """)

    # ── Raw Statement Persistence ────────────────────────────────

    async def add_raw_statement(self, source: str, raw_data: dict) -> None:
        """Persist a raw bank statement JSON."""
        await asyncio.to_thread(self._add_raw_statement_sync, source, raw_data)

    def _add_raw_statement_sync(self, source: str, raw_data: dict):
        self.conn.execute(
            "INSERT INTO raw_statements VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            [str(uuid.uuid4()), source, json.dumps(raw_data, cls=_DomainEncoder)],
        )

    # ── Core CRUD ────────────────────────────────────────────────

    async def add_transactions(self, transactions: List[Transaction]) -> None:
        await asyncio.to_thread(self._add_transactions_sync, transactions)

    def _add_transactions_sync(self, transactions: List[Transaction]):
        rows = [
            (
                str(t.id),
                str(t.account_id),
                t.category.name if t.category else None,
                float(t.amount),
                t.currency.value,
                t.description,
                t.timestamp,
                t.merchant,
            )
            for t in transactions
        ]
        self.conn.executemany("""
        INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    async def get_transactions(
        self,
        account_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Transaction]:
        return await asyncio.to_thread(self._get_transactions_sync, account_id, start_date, end_date)

    def _get_transactions_sync(self, account_id, start_date, end_date):
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list = []

        if account_id:
            query += " AND account_id = ?"
            params.append(str(account_id))

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_domain(r) for r in rows]

    # ── Analytics Queries ────────────────────────────────────────

    async def get_monthly_spend(self, year: int, month: int) -> Decimal:
        return await asyncio.to_thread(self._get_monthly_spend_sync, year, month)

    def _get_monthly_spend_sync(self, year, month):
        result = self.conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE EXTRACT(year FROM timestamp) = ?
          AND EXTRACT(month FROM timestamp) = ?
          AND amount < 0
        """, [year, month]).fetchone()[0]
        return Decimal(str(result))

    async def search_transactions(self, query: str, limit: int = 50) -> List[Transaction]:
        return await asyncio.to_thread(self._search_transactions_sync, query, limit)

    def _search_transactions_sync(self, query, limit):
        rows = self.conn.execute("""
        SELECT * FROM transactions
        WHERE description ILIKE ? OR merchant ILIKE ?
        ORDER BY timestamp DESC
        LIMIT ?
        """, [f"%{query}%", f"%{query}%", limit]).fetchall()
        return [self._row_to_domain(r) for r in rows]

    async def get_category_breakdown(self, year: int, month: int) -> List[CategoryBreakdown]:
        return await asyncio.to_thread(self._get_category_breakdown_sync, year, month)

    def _get_category_breakdown_sync(self, year, month):
        rows = self.conn.execute("""
        SELECT
            COALESCE(category, 'Uncategorised') AS cat,
            SUM(amount) AS total,
            COUNT(*) AS cnt
        FROM transactions
        WHERE EXTRACT(year FROM timestamp) = ?
          AND EXTRACT(month FROM timestamp) = ?
          AND amount < 0
        GROUP BY cat
        ORDER BY total ASC
        """, [year, month]).fetchall()
        return [
            CategoryBreakdown(category=r[0], total_amount=Decimal(str(r[1])), transaction_count=r[2])
            for r in rows
        ]

    async def get_top_merchants(self, year: int, month: int, limit: int = 10) -> List[tuple[str, Decimal]]:
        return await asyncio.to_thread(self._get_top_merchants_sync, year, month, limit)

    def _get_top_merchants_sync(self, year, month, limit):
        rows = self.conn.execute("""
        SELECT merchant, SUM(amount) AS total
        FROM transactions
        WHERE EXTRACT(year FROM timestamp) = ?
          AND EXTRACT(month FROM timestamp) = ?
          AND amount < 0
          AND merchant IS NOT NULL
        GROUP BY merchant
        ORDER BY total ASC
        LIMIT ?
        """, [year, month, limit]).fetchall()
        return [(r[0], Decimal(str(r[1]))) for r in rows]

    async def get_cashflow_summary(self, year: int, month: int) -> MonthlySummary:
        return await asyncio.to_thread(self._get_cashflow_summary_sync, year, month)

    def _get_cashflow_summary_sync(self, year, month):
        row = self.conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS income,
            COALESCE(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE EXTRACT(year FROM timestamp) = ?
          AND EXTRACT(month FROM timestamp) = ?
        """, [year, month]).fetchone()

        income = Decimal(str(row[0]))
        expenses = Decimal(str(row[1]))

        # Get top categories for context
        categories = self._get_category_breakdown_sync(year, month)

        return MonthlySummary(
            year=year,
            month=month,
            income=income,
            expenses=expenses,
            net=income + expenses,
            top_categories=categories[:5],
        )

    # ── Row Mapping ──────────────────────────────────────────────

    def _row_to_domain(self, row) -> Transaction:
        return Transaction(
            id=uuid.UUID(row[0]),
            account_id=uuid.UUID(row[1]),
            category=Category(id=uuid.uuid4(), name=row[2]) if row[2] else None,
            amount=Decimal(str(row[3])),
            currency=row[4],
            description=row[5],
            timestamp=row[6],
            merchant=row[7],
        )

    # ── Deletion ─────────────────────────────────────────────────

    async def delete_all_transactions(self) -> int:
        """Delete all transactions and return count deleted."""
        return await asyncio.to_thread(self._delete_all_sync)

    def _delete_all_sync(self) -> int:
        count = self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        self.conn.execute("DELETE FROM transactions")
        return count

    async def delete_last_n_transactions(self, n: int) -> int:
        """Delete the last n transactions (most recent first). Return count deleted."""
        return await asyncio.to_thread(self._delete_last_n_sync, n)

    def _delete_last_n_sync(self, n: int) -> int:
        # Get IDs of the N most recent transactions
        rows = self.conn.execute(
            "SELECT id FROM transactions ORDER BY timestamp DESC LIMIT ?", [n]
        ).fetchall()
        if not rows:
            return 0
        ids = [r[0] for r in rows]
        placeholders = ", ".join(["?"] * len(ids))
        self.conn.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", ids)
        return len(ids)

    # ── Lifecycle ────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the DuckDB connection."""
        self.conn.close()
