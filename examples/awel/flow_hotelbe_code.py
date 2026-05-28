"""AWEL: Hotel-be code assistant.

Uses registered hotel-be file tools to answer code questions.
Auto-loaded by DB-GPT on startup.

Usage:
    curl -X POST http://localhost:5670/api/v1/awel/trigger/examples/hotelbe_code \
      -H "Content-Type: application/json" \
      -d '{"model": "deepseek-chat", "user_input": "How does KnowledgeSyncConfig work?"}'
"""

import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.model.operators import LLMOperator

logger = logging.getLogger(__name__)


class TriggerReqBody(BaseModel):
    model: str = Field(default="deepseek-chat", description="Model name")
    user_input: str = Field(..., description="User question about hotel-be code")


class HotelbeCodeOperator(MapOperator[TriggerReqBody, ModelRequest]):
    """Gather hotel-be context using file tools, then build LLM request."""

    SYSTEM_PROMPT = """You are a hotel-be code expert. You have access to the full hotel-be repository.

Rules:
1. Answer questions based on actual code in the repository.
2. When you find relevant code, quote file paths and line numbers.
3. If you cannot find relevant files say so, then answer from general knowledge.
4. Always provide concrete code examples when discussing implementation details."""

    async def map(self, input_value: TriggerReqBody) -> ModelRequest:
        question = input_value.user_input.strip()
        context = self._gather_context(question)

        sys_msg = self.SYSTEM_PROMPT + "\n\n## Project Context\n" + context

        messages = [
            ModelMessage.build_system_message(sys_msg),
            ModelMessage.build_human_message(question),
        ]
        return ModelRequest.build_request(input_value.model, messages)

    def _gather_context(self, question: str) -> str:
        """Search hotel-be codebase using registered tools, return markdown context."""
        from dbgpt_ext.datasource.tool_hotelbe import (
            hotelbe_grep_code,
            hotelbe_list_files,
            hotelbe_read_file,
            hotelbe_search_files,
        )

        parts = []

        keywords = self._extract_keywords(question)

        # Search by content keyword
        for kw in keywords:
            try:
                result = hotelbe_search_files(keyword=kw, max_results=10)
                parts.append(f"### Search results for '{kw}'\n{result}\n")
            except Exception as e:
                logger.warning("search keyword %s failed: %s", kw, e)

        # Grep for Go symbols
        for kw in keywords:
            try:
                result = hotelbe_grep_code(symbol=kw)
                parts.append(f"### Go symbol search for '{kw}'\n{result}\n")
            except Exception as e:
                logger.warning("grep symbol %s failed: %s", kw, e)

        # Strip to avoid overwhelming the LLM
        combined = "\n".join(parts)
        if len(combined) > 15000:
            combined = combined[:15000] + "\n\n...(truncated)"

        return combined if combined else "(No relevant project context found)"

    @staticmethod
    def _extract_keywords(question: str) -> list:
        """Extract probable code symbols from a natural language question."""
        import re

        # CamelCase symbols
        symbols = re.findall(r"[A-Z][a-zA-Z0-9]+", question)

        # Snake_case or dot-separated paths
        symbols += re.findall(r"[a-z]+_[a-z_]+", question)
        symbols += re.findall(r"[a-zA-Z0-9]+\.[a-zA-Z0-9.]+", question)

        # Single important words (Go-influenced)
        go_keywords = {"struct", "interface", "func", "method", "package", "module",
                       "service", "handler", "config", "route", "middleware", "model",
                       "dao", "repo", "api", "db", "sql", "cache", "queue", "job"}
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question.lower())
        for w in words:
            if w in go_keywords:
                symbols.append(w)

        # Deduplicate, limit
        seen = set()
        result = []
        for s in symbols:
            if s not in seen and len(s) > 1:
                seen.add(s)
                result.append(s)
        return result[:5]


with DAG("dbgpt_awel_hotelbe_code_assistant") as dag:
    trigger = HttpTrigger(
        "/examples/hotelbe_code",
        methods="POST",
        request_body=TriggerReqBody,
    )
    code_op = HotelbeCodeOperator()
    llm_task = LLMOperator(task_name="llm_task")
    output = MapOperator(lambda out: out.to_dict())
    trigger >> code_op >> llm_task >> output
