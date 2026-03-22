"""End-to-end ingestion pipeline: PDF → extract → LLM raw → LLM map → validate → persist."""

import uuid

from money_manager.domain.interfaces import LLMClient, TransactionRepository
from money_manager.domain.models import IngestionResult
from money_manager.tools.ingestion.llm_raw_extractor import extract_raw_transactions
from money_manager.tools.ingestion.llm_schema_mapper import map_to_canonical
from money_manager.tools.ingestion.pdf_extractor import extract_text_from_pdf
from money_manager.tools.ingestion.validator import validate_transactions


async def ingest_pdf(
    file_bytes: bytes,
    source: str,
    repo: TransactionRepository,
    llm: LLMClient,
    account_id: uuid.UUID,
    password: str | None = None,
) -> IngestionResult:
    """
    Full ingestion pipeline for a PDF bank statement.

    Steps:
        1. Extract text from PDF
        2. LLM extracts raw transaction rows
        3. LLM maps raw rows to canonical schema
        4. Pydantic validates each transaction
        5. Valid transactions persisted to DB
        6. Raw statement JSON archived

    Args:
        file_bytes: Raw PDF bytes.
        source: Human-readable source name (e.g. "HDFC_Jan2024.pdf").
        repo: Transaction repository for persistence.
        llm: LLM client for extraction and mapping.
        account_id: UUID of the account to associate transactions with.

    Returns:
        IngestionResult with counts and any rejected rows.
    """
    # Step 1: PDF → text
    text = extract_text_from_pdf(file_bytes, password=password)

    # Step 2: LLM raw extraction
    raw_rows = await extract_raw_transactions(text, llm)

    # Step 3: LLM schema mapping (separate call)
    mapped_rows = await map_to_canonical(raw_rows, llm, account_id)

    # Step 4: Pydantic validation
    valid_txns, rejected = validate_transactions(mapped_rows)

    # Step 5: Persist valid transactions
    if valid_txns:
        await repo.add_transactions(valid_txns)

    # Step 6: Archive raw statement
    if hasattr(repo, "add_raw_statement"):
        await repo.add_raw_statement(source, {"raw_rows": raw_rows, "mapped_rows": mapped_rows})

    return IngestionResult(
        source=source,
        total_extracted=len(raw_rows),
        valid_count=len(valid_txns),
        rejected_count=len(rejected),
        rejected_rows=rejected,
    )
