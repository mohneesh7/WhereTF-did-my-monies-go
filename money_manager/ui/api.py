"""FastAPI backend – REST endpoints for the money manager."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from pydantic import BaseModel

from money_manager.app.agent import FinanceAgent
from money_manager.config import settings
from money_manager.tools.db import DuckDBTransactionRepository
from money_manager.tools.llm import LiteLLMClient
from money_manager.tools.ingestion.pipeline import ingest_pdf


# ── Shared State ─────────────────────────────────────────────────

repo: DuckDBTransactionRepository | None = None
llm: LiteLLMClient | None = None
agent: FinanceAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise DB + LLM on startup, close on shutdown.

    Skips initialization if globals are already set (e.g. during tests).
    """
    global repo, llm, agent
    pre_set = repo is not None  # True when tests inject their own repo
    if not pre_set:
        repo = DuckDBTransactionRepository(settings.DB_PATH)
        llm = LiteLLMClient()
        agent = FinanceAgent(repo, llm)
    yield
    if repo and not pre_set:
        await repo.close()


app = FastAPI(
    title="WhereTF Did My Monies Go",
    description="Agentic money manager – ingest statements, analyse spending, chat with your finances",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Request / Response Schemas ───────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    current_date: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


class HealthResponse(BaseModel):
    status: str
    db: str
    llm: str


# ── Endpoints ────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Check system health."""
    llm_ok = False
    try:
        if llm:
            llm_ok = await llm.health_check()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        db="connected" if repo else "disconnected",
        llm="connected" if llm_ok else "disconnected",
    )


@app.post("/api/ingest")
async def ingest_statement(
    file: UploadFile = File(...),
    account_id: str = Query(default=None, description="Account UUID (auto-generated if omitted)"),
    password: str = Query(default=None, description="Password for encrypted PDFs"),
):
    """Upload a PDF bank statement for ingestion."""
    if not repo or not llm:
        raise HTTPException(status_code=503, detail="Service not ready")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    acc_id = uuid.UUID(account_id) if account_id else uuid.uuid4()
    file_bytes = await file.read()

    try:
        result = await ingest_pdf(
            file_bytes=file_bytes,
            source=file.filename,
            repo=repo,
            llm=llm,
            account_id=acc_id,
            password=password,
        )
        return {
            "status": "success",
            "account_id": str(acc_id),
            "source": result.source,
            "total_extracted": result.total_extracted,
            "valid_count": result.valid_count,
            "rejected_count": result.rejected_count,
            "rejected_rows": result.rejected_rows,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.get("/api/transactions")
async def list_transactions(
    account_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """List transactions with optional filters."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")

    acc = uuid.UUID(account_id) if account_id else None
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None

    txns = await repo.get_transactions(account_id=acc, start_date=start, end_date=end)
    return [
        {
            "id": str(t.id),
            "account_id": str(t.account_id),
            "amount": float(t.amount),
            "currency": t.currency.value,
            "description": t.description,
            "timestamp": t.timestamp.isoformat(),
            "merchant": t.merchant,
            "category": t.category.name if t.category else None,
        }
        for t in txns
    ]


@app.get("/api/analytics/monthly/{year}/{month}")
async def monthly_spend(year: int, month: int):
    """Get total spend for a month."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")

    spend = await repo.get_monthly_spend(year, month)
    return {"year": year, "month": month, "total_spend": float(spend), "currency": "INR"}


@app.get("/api/analytics/categories/{year}/{month}")
async def category_breakdown(year: int, month: int):
    """Get spend breakdown by category for a month."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")

    breakdown = await repo.get_category_breakdown(year, month)
    return [
        {
            "category": b.category,
            "total_amount": float(b.total_amount),
            "transaction_count": b.transaction_count,
        }
        for b in breakdown
    ]


@app.get("/api/analytics/cashflow/{year}/{month}")
async def cashflow_summary(year: int, month: int):
    """Get income vs expenses summary for a month."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")

    summary = await repo.get_cashflow_summary(year, month)
    return {
        "year": summary.year,
        "month": summary.month,
        "income": float(summary.income),
        "expenses": float(summary.expenses),
        "net": float(summary.net),
    }


@app.get("/api/analytics/merchants/{year}/{month}")
async def top_merchants(year: int, month: int, limit: int = Query(10, ge=1, le=50)):
    """Get top merchants by spend for a month."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")

    merchants = await repo.get_top_merchants(year, month, limit)
    return [{"merchant": name, "total_spend": float(amount)} for name, amount in merchants]


@app.delete("/api/transactions")
async def delete_all_transactions():
    """Delete every transaction from the database."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")
    count = await repo.delete_all_transactions()
    return {"status": "ok", "deleted": count}


@app.delete("/api/transactions/last/{n}")
async def delete_last_n_transactions(n: int):
    """Delete the last N transactions (most recent first)."""
    if not repo:
        raise HTTPException(status_code=503, detail="Service not ready")
    if n < 1:
        raise HTTPException(status_code=400, detail="n must be >= 1")
    count = await repo.delete_last_n_transactions(n)
    return {"status": "ok", "deleted": count}


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Chat with the finance agent."""
    if not agent:
        raise HTTPException(status_code=503, detail="Service not ready")

    reply = await agent.chat(request.message, current_date=request.current_date)
    return ChatResponse(reply=reply)
