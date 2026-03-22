"""Centralized configuration for the money manager application."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # ── Database ──────────────────────────────────────────────
    DB_PATH: Path = Path(os.getenv("MM_DB_PATH", "money.duckdb"))

    # ── LLM (LiteLLM – provider-agnostic) ─────────────────────
    #   Examples:
    #     gpt-4o              → OpenAI
    #     ollama/llama3       → local Ollama
    #     gemini/gemini-pro   → Google Gemini
    #     anthropic/claude-3  → Anthropic
    #     hosted_vllm/model   → self-hosted vLLM
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
    LLM_API_BASE: str | None = os.getenv("LLM_API_BASE")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

    # ── UPI / Transaction Identifiers ────────────────────────
    #   Comma-separated narration prefixes that denote UPI transactions.
    #   Override via env: UPI_IDENTIFIERS=UPIOUT,UPIAR,UPI/DR,UPI/CR
    UPI_IDENTIFIERS: list[str] = [
        x.strip()
        for x in os.getenv("UPI_IDENTIFIERS", "UPIOUT,UPIAR").split(",")
        if x.strip()
    ]

    # ── API ───────────────────────────────────────────────────
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))


settings = Settings()


# ── Reusable UPI narration guide for LLM prompts ─────────────
UPI_NARRATION_GUIDE = f"""
UPI Transaction Handling
========================
The following narration prefixes indicate UPI transactions: {", ".join(settings.UPI_IDENTIFIERS)}.

Narration format (slash-separated):
  <TYPE>/<TxnID>/<BeneficiaryName>/<BankCode>/<AccountDigits>/<Purpose>
  Example: UPIOUT/800412179072/BuntyG/IOBA/123412341234/Mutual Fund

Rules:
1. **Merchant**: Use the beneficiary name (3rd segment) as the merchant.
2. **Description**: Use the purpose (last segment) as the description.
   - If the purpose is missing, empty, or ends with '@' (e.g. an email/UPI handle),
     set description to "<TYPE>-Others" (e.g. "UPI-DEBIT-Others").
3. **Amount sign**: UPIOUT/ UPIAR / DR → negative (debit), UPIREV/ UPIAB / CR → positive (credit).
"""
