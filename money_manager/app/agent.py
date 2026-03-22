"""LLM-based finance agent – plans which tool to call, executes, and synthesizes a response.

Architecture:
    1. Planner: LLM picks which deterministic tool to call + params
    2. Executor: Runs the selected tool (no raw SQL)
    3. Synthesizer: LLM turns tool results into a natural language answer
"""

import json
from typing import Optional

from money_manager.app.tools import TOOL_REGISTRY
from money_manager.domain.interfaces import LLMClient, TransactionRepository


PLANNER_SYSTEM_PROMPT = """You are a financial assistant that helps users understand their spending.
You have access to these tools to answer questions:

{tool_descriptions}

When the user asks a question, decide which tool to call and return ONLY valid JSON:
{{
    "tool": "tool_name",
    "params": {{"param1": value1, "param2": value2}}
}}

If the user's question doesn't require a tool (e.g. greetings, general advice), return:
{{
    "tool": null,
    "params": {{}}
}}

Important:
- Use the current date context to infer year/month if not specified.
- For "last month" or "this month", calculate from the current date.
- Always pick the MOST relevant tool for the question.
- Return ONLY the JSON object, no other text."""

SYNTHESIZER_SYSTEM_PROMPT = """You are a friendly, knowledgeable financial assistant.
Given the user's question and the data from our analytics tools, provide a clear,
helpful, and conversational response. Include specific numbers and insights.
If there are opportunities to save money or optimize spending, mention them.
Keep responses concise but informative. Use bullet points for lists.
Format currency values appropriately (e.g. ₹1,234.56 for INR)."""


class FinanceAgent:
    """LLM-powered agent that answers finance questions using deterministic tools."""

    def __init__(self, repo: TransactionRepository, llm: LLMClient):
        self.repo = repo
        self.llm = llm

    async def chat(self, message: str, current_date: Optional[str] = None) -> str:
        """
        Process a user message through the plan → execute → synthesize pipeline.

        Args:
            message: User's question or message.
            current_date: ISO date string for context (defaults to today).

        Returns:
            Natural language response.
        """
        from datetime import datetime

        if current_date is None:
            current_date = datetime.now().strftime("%Y-%m-%d")

        # ── Step 1: Plan ─────────────────────────────────────────
        tool_descriptions = self._build_tool_descriptions()
        planner_prompt = PLANNER_SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)

        plan_input = f"Current date: {current_date}\nUser question: {message}"

        try:
            if hasattr(self.llm, "generate_json"):
                plan = await self.llm.generate_json(plan_input, system_prompt=planner_prompt)
            else:
                plan_text = await self.llm.generate_text(plan_input, system_prompt=planner_prompt)
                plan = json.loads(plan_text)
        except (json.JSONDecodeError, Exception):
            # If planning fails, respond conversationally without tools
            return await self._direct_response(message, current_date)

        tool_name = plan.get("tool")
        params = plan.get("params", {})

        # ── Step 2: Execute ──────────────────────────────────────
        if tool_name is None or tool_name not in TOOL_REGISTRY:
            return await self._direct_response(message, current_date)

        tool_entry = TOOL_REGISTRY[tool_name]
        tool_fn = tool_entry["function"]

        try:
            # Call the tool with the repo and LLM-selected params
            result = await tool_fn(self.repo, **params)
        except Exception as e:
            result = json.dumps({"error": f"Tool execution failed: {str(e)}"})

        # ── Step 3: Synthesize ───────────────────────────────────
        synthesis_prompt = (
            f"User asked: {message}\n\n"
            f"Tool used: {tool_name}\n"
            f"Tool result:\n{result}\n\n"
            f"Please provide a helpful, conversational response based on this data."
        )

        response = await self.llm.generate_text(synthesis_prompt, system_prompt=SYNTHESIZER_SYSTEM_PROMPT)
        return response

    async def _direct_response(self, message: str, current_date: str) -> str:
        """Handle messages that don't need tool calls (greetings, advice, etc)."""
        prompt = (
            f"Current date: {current_date}\n"
            f"You are a helpful financial assistant. The user said: {message}\n\n"
            f"Respond conversationally. If they seem to be asking about their finances "
            f"but the question is vague, ask clarifying questions about what month/year "
            f"or category they're interested in."
        )
        return await self.llm.generate_text(prompt, system_prompt=SYNTHESIZER_SYSTEM_PROMPT)

    def _build_tool_descriptions(self) -> str:
        """Format tool registry as text for the planner prompt."""
        lines = []
        for name, info in TOOL_REGISTRY.items():
            params_str = ", ".join(
                f"{k}: {v['type']}" + (" (optional)" if v.get("optional") else "")
                for k, v in info["parameters"].items()
            )
            lines.append(f"- {name}({params_str}): {info['description']}")
        return "\n".join(lines)
