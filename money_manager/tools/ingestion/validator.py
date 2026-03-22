"""Pydantic validation of transaction dicts before persistence."""

from typing import Any

from money_manager.domain.models import Category, Transaction


def validate_transactions(
    raw_dicts: list[dict[str, Any]],
) -> tuple[list[Transaction], list[dict[str, Any]]]:
    """
    Validate a list of raw transaction dicts against the Transaction schema.

    Args:
        raw_dicts: List of dicts from the LLM schema mapper.

    Returns:
        Tuple of (valid_transactions, rejected_rows).
        Each rejected row includes an 'error' field describing what failed.
    """
    valid: list[Transaction] = []
    rejected: list[dict[str, Any]] = []

    for row in raw_dicts:
        try:
            # Handle category as a simple name string → Category model
            if isinstance(row.get("category"), str):
                row["category"] = Category(name=row["category"])

            txn = Transaction(**row)
            valid.append(txn)
        except Exception as e:
            rejected.append({**row, "error": str(e)})

    return valid, rejected
