"""Bridge the serving LLM to the sync ``prompt -> str`` callable used by the
L2 annotator / L3 metric miner.

``build_sync_llm()`` resolves the server's default model (``CFG.LLM_MODEL``
+ worker manager) and returns ``None`` when unavailable, so callers degrade
to heuristic mode. The returned callable runs its own event loop via
``asyncio.run`` and must therefore be invoked from a worker thread (the
``/drafts`` endpoint hops via ``asyncio.to_thread``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def build_sync_llm_from_client(client: Any, model_name: str) -> Callable[[str], str]:
    """Wrap an async LLMClient into a sync callable (call from a thread)."""

    def llm(prompt: str) -> str:
        async def _call() -> str:
            from dbgpt.core import ModelRequest

            request = ModelRequest.build_request(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_new_tokens=2048,
            )
            output = await client.generate(request)
            return output.text or ""

        return asyncio.run(_call())

    return llm


def build_sync_llm() -> Optional[Callable[[str], str]]:
    """Resolve the serving default LLM; None when unavailable (heuristic)."""
    try:
        from dbgpt._private.config import Config
        from dbgpt.component import ComponentType
        from dbgpt.model import DefaultLLMClient
        from dbgpt.model.cluster import WorkerManagerFactory

        cfg = Config()
        system_app = cfg.SYSTEM_APP
        model_name = getattr(cfg, "LLM_MODEL", None)
        if system_app is None or not model_name:
            return None
        worker_manager = system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        client = DefaultLLMClient(worker_manager, auto_convert_message=True)
        return build_sync_llm_from_client(client, model_name)
    except Exception as e:  # noqa: BLE001 - bridge is best-effort by design
        logger.warning(f"llm bridge unavailable, fallback to heuristic: {e}")
        return None
