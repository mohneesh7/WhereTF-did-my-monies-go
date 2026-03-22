"""LiteLLM-based LLM client – provider-agnostic (OpenAI, Gemini, Anthropic, Ollama, vLLM, Groq, etc)."""

import json
import os
from typing import List, Optional

import litellm

from money_manager.config import settings
from money_manager.domain.interfaces import LLMClient

# Map LiteLLM model prefixes to the env var name LiteLLM expects for each provider
_PROVIDER_KEY_ENV_VARS: dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "cohere": "COHERE_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


class LiteLLMClient(LLMClient):
    """
    Provider-agnostic LLM client powered by LiteLLM.

    Switch providers by changing the LLM_MODEL env var:
        gpt-4o                      → OpenAI
        groq/llama-3.3-70b-versatile → Groq
        ollama/llama3               → local Ollama
        gemini/gemini-pro           → Google Gemini
        anthropic/claude-3          → Anthropic
        hosted_vllm/model           → self-hosted vLLM
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float | None = None,
    ):
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY
        self.api_base = api_base or settings.LLM_API_BASE
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE

        # LiteLLM requires provider-specific env vars (e.g. GROQ_API_KEY).
        # Set them from our unified LLM_API_KEY config.
        if self.api_key:
            prefix = self.model.split("/")[0].lower() if "/" in self.model else "openai"
            env_var = _PROVIDER_KEY_ENV_VARS.get(prefix)
            if env_var and not os.environ.get(env_var):
                os.environ[env_var] = self.api_key

        # Silence litellm verbose logging
        litellm.set_verbose = False

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a chat completion via LiteLLM."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            api_key=self.api_key,
            api_base=self.api_base,
            num_retries=3,  # Automatically retry on rate limits with exponential backoff
        )
        return response.choices[0].message.content

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> dict | list:
        """Generate text and parse as JSON. Retries once on parse failure."""
        text = await self.generate_text(prompt, system_prompt)

        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (the fences)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Retry with explicit JSON instruction
            retry_prompt = (
                f"The following text should be valid JSON but failed to parse. "
                f"Please return ONLY valid JSON, no markdown fences:\n\n{text}"
            )
            retry_text = await self.generate_text(retry_prompt)
            retry_cleaned = retry_text.strip()
            if retry_cleaned.startswith("```"):
                lines = retry_cleaned.split("\n")
                lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                retry_cleaned = "\n".join(lines)
            return json.loads(retry_cleaned)

    async def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via LiteLLM."""
        response = await litellm.aembedding(
            model=self.model,
            input=texts,
            api_key=self.api_key,
            api_base=self.api_base,
        )
        return [item["embedding"] for item in response.data]

    async def health_check(self) -> bool:
        """Verify the LLM is reachable by sending a minimal request."""
        try:
            await self.generate_text("ping")
            return True
        except Exception:
            return False
