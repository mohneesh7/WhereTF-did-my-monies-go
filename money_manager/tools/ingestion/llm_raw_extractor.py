"""LLM-powered extraction of raw transaction rows from statement text."""

from money_manager.config import UPI_NARRATION_GUIDE
from money_manager.domain.interfaces import LLMClient

SYSTEM_PROMPT = f"""You are a financial data extraction assistant.
Your job is to extract individual transactions from bank statement text.
Return ONLY a valid JSON array of objects. No markdown, no explanation.

Each object should have these fields (use null if not found):
- "date": string in YYYY-MM-DD format
- "description": the transaction narration/description
- "amount": numeric value (positive for credits, negative for debits)
- "type": "credit" or "debit"
- "reference": any reference number if present
- "balance": running balance if shown

{UPI_NARRATION_GUIDE}

Example output:
[
  {{"date": "2024-01-15", "description": "Swiggy order", "amount": -450.00, "type": "debit", "reference": "UPI123", "balance": 25000.00, "merchant": "Swiggy"}},
  {{"date": "2024-01-16", "description": "SALARY", "amount": 50000.00, "type": "credit", "reference": null, "balance": 75000.00, "merchant": null}},
  {{"date": "2024-01-17", "description": "UPI-DEBIT-Others", "amount": -200.00, "type": "debit", "reference": "UPI456", "balance": 24800.00, "merchant": "BuntyG"}}
]"""


async def extract_raw_transactions(text: str, llm: LLMClient) -> list[dict]:
    """
    Send statement text to LLM and extract raw transaction rows.

    Args:
        text: Full text extracted from bank statement PDF.
        llm: An LLMClient instance (any provider).

    Returns:
        List of raw transaction dicts as extracted by the LLM.
    """
    # For very long statements, truncate to avoid token limits
    max_chars = 15000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... truncated ...]"

    prompt = f"Extract all transactions from this bank statement:\n\n{text}"

    # Use generate_json if available (LiteLLMClient has it), else fallback
    if hasattr(llm, "generate_json"):
        result = await llm.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
    else:
        import json
        raw = await llm.generate_text(prompt, system_prompt=SYSTEM_PROMPT)
        result = json.loads(raw)

    if not isinstance(result, list):
        raise ValueError(f"LLM returned non-list type: {type(result)}")

    return result
