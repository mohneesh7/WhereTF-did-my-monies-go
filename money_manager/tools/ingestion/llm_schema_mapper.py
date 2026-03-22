"""LLM-powered mapping of raw transaction rows to the canonical Transaction schema."""

import uuid

from money_manager.config import UPI_NARRATION_GUIDE
from money_manager.domain.interfaces import LLMClient

SYSTEM_PROMPT = f"""You are a financial data normalization assistant.
Your job is to take raw transaction rows and map them to a canonical schema.
Return ONLY a valid JSON array of objects. No markdown, no explanation.

Each object MUST have these fields:
- "amount": signed decimal (negative for debits/spend, positive for credits/income)
- "description": cleaned up transaction narration
- "currency": "INR" or "USD" (default "INR" if unclear)
- "timestamp": ISO 8601 datetime string (e.g. "2024-01-15T00:00:00")
- "merchant": extracted merchant name if identifiable, else null
- "category": best-guess category from this list:
    Food, Transport, Shopping, Bills, Entertainment, Health, Education,
    Salary, Transfer, Investment, ATM, EMI, Groceries, Travel, Other

{UPI_NARRATION_GUIDE}

Example output:
[
  {{"amount": -450.00, "description": "Swiggy order", "currency": "INR", "timestamp": "2024-01-15T00:00:00", "merchant": "Swiggy", "category": "Food"}},
  {{"amount": 50000.00, "description": "Monthly salary", "currency": "INR", "timestamp": "2024-01-16T00:00:00", "merchant": null, "category": "Salary"}},
  {{"amount": -200.00, "description": "UPI-DEBIT-Others", "currency": "INR", "timestamp": "2024-01-17T00:00:00", "merchant": "BuntyG", "category": "Transfer"}}
]"""


async def map_to_canonical(
    raw_rows: list[dict],
    llm: LLMClient,
    account_id: uuid.UUID,
) -> list[dict]:
    """
    Map raw LLM-extracted rows to canonical Transaction schema fields.

    This is a SEPARATE LLM call from extraction – it focuses on
    normalization, categorization, and merchant identification.

    Args:
        raw_rows: Raw transaction dicts from llm_raw_extractor.
        llm: An LLMClient instance.
        account_id: UUID of the account these transactions belong to.

    Returns:
        List of dicts ready for Pydantic validation.
    """
    import json

    prompt = (
        f"Normalize these raw bank transactions into the canonical schema.\n\n"
        f"Raw transactions:\n{json.dumps(raw_rows, indent=2)}"
    )

    if hasattr(llm, "generate_json"):
        mapped = await llm.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
    else:
        raw_text = await llm.generate_text(prompt, system_prompt=SYSTEM_PROMPT)
        mapped = json.loads(raw_text)

    if not isinstance(mapped, list):
        raise ValueError(f"LLM returned non-list type: {type(mapped)}")

    # Inject account_id into each row
    for row in mapped:
        row["account_id"] = str(account_id)

    return mapped
