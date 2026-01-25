import duckdb
import asyncio
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
import uuid

from money_manager.domain.interfaces import TransactionRepository
from money_manager.domain.models import Transaction, Category


DB_PATH = Path("money.duckdb")


class DuckDBTransactionRepository(TransactionRepository):
    def __init__(self, db_path: str | Path = DB_PATH):
        self.conn = duckdb.connect(str(db_path))
        self._init_tables()

    # ---------------- Tables ---------------- #

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

    # ---------------- Raw Ingestion ---------------- #

    def add_raw_statement(self, source: str, raw_data: dict):
        self.conn.execute(
            "INSERT INTO raw_statements VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            [str(uuid.uuid4()), source, raw_data]
        )

    # ---------------- Core Interface ---------------- #

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
        params = []

        if account_id:
            query += " AND account_id = ?"
            params.append(str(account_id))

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_domain(r) for r in rows]

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

        return Decimal(result)

    async def search_transactions(self, query: str, limit: int = 50) -> List[Transaction]:
        return await asyncio.to_thread(self._search_transactions_sync, query, limit)

    def _search_transactions_sync(self, query, limit):
        rows = self.conn.execute("""
        SELECT * FROM transactions
        WHERE description ILIKE ?
        ORDER BY timestamp DESC
        LIMIT ?
        """, [f"%{query}%", limit]).fetchall()

        return [self._row_to_domain(r) for r in rows]

    # ---------------- Mapping ---------------- #

    def _row_to_domain(self, row):
        return Transaction(
            id=uuid.UUID(row[0]),
            account_id=uuid.UUID(row[1]),
            category=Category(id=uuid.uuid4(), name=row[2]) if row[2] else None,
            amount=Decimal(row[3]),
            currency=row[4],
            description=row[5],
            timestamp=row[6],
            merchant=row[7],
        )
