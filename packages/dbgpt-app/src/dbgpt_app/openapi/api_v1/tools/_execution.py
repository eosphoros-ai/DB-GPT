"""Shared runtime selection and session lifecycle for agent execution tools."""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Iterable, Optional

from dbgpt_sandbox.sandbox.config import SANDBOX_AGENT_IMAGE
from dbgpt_sandbox.sandbox.execution_layer.base import (
    ExecutionResult,
    ExecutionStatus,
    SessionConfig,
)
from dbgpt_sandbox.sandbox.execution_layer.runtime_factory import RuntimeFactory

logger = logging.getLogger(__name__)


def _input_paths(env: Dict[str, str], extra: Iterable[str]) -> list[str]:
    paths = list(extra)
    if env.get("FILE_PATH"):
        paths.append(env["FILE_PATH"])
    if env.get("FILES_JSON"):
        paths.append(env["FILES_JSON"])
        mapping = json.loads(Path(env["FILES_JSON"]).read_text(encoding="utf-8"))
        if not isinstance(mapping, dict) or any(
            not isinstance(path, str) for path in mapping.values()
        ):
            raise ValueError("Invalid execution file mapping")
        paths.extend(mapping.values())
    return list(dict.fromkeys(os.path.abspath(path) for path in paths))


def _normalize_result(result) -> ExecutionResult:
    if isinstance(result, ExecutionResult):
        return result
    # Container backends historically return DisplayResult with string status.
    return ExecutionResult(
        status=ExecutionStatus(result.status),
        output=result.output or "",
        error=result.error or "",
        exit_code=result.exit_code,
        execution_time=result.execution_time,
    )


async def _dispose(runtime, session_id: str) -> None:
    try:
        await runtime.destroy_session(session_id)
    except Exception:
        logger.warning("Failed to destroy session %s", session_id, exc_info=True)
    finally:
        if runtime.runtime_id == "docker":
            try:
                await asyncio.to_thread(runtime.docker_client.close)
            except Exception:
                logger.warning("Failed to close Docker client", exc_info=True)


async def run_code(
    code: str,
    *,
    language: str,
    work_dir: str,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    input_paths: Iterable[str] = (),
) -> ExecutionResult:
    """Run once, collect artifacts, and clean up on success/error/cancellation.

    An explicitly configured container must be available. Initialization,
    session creation, execution and artifact failures never trigger a local
    retry. Local execution is only selected by the default or explicit config.
    """
    environment = dict(env or {})
    work_dir = os.path.abspath(work_dir)
    os.makedirs(work_dir, exist_ok=True)
    config = SessionConfig(
        language=language,
        working_dir=work_dir,
        host_working_dir=work_dir,
        input_files=_input_paths(environment, input_paths),
        environment_vars=environment,
        timeout=timeout,
        max_memory=512 * 1024 * 1024 if language == "python" else 256 * 1024 * 1024,
        image=SANDBOX_AGENT_IMAGE,
        # Preserve the Python tool's existing arbitrary-code behavior, including
        # os/pandas imports and file IO. Local mode is not a security boundary.
        validate_code=language != "python",
    )
    session_id = f"agent_{uuid.uuid4().hex}"
    runtime = await asyncio.to_thread(RuntimeFactory.create)
    try:
        session = await runtime.create_session(session_id, config)
        logger.info(
            "Sandbox execution: runtime=%s language=%s session_id=%s",
            runtime.runtime_id,
            language,
            session_id,
        )
        result = _normalize_result(await session.execute(code))
        collect_artifacts = getattr(session, "collect_artifacts", None)
        if collect_artifacts:
            try:
                await collect_artifacts()
            except Exception as exc:
                # Keep stdout, but don't claim the output files were saved.
                result.status = ExecutionStatus.ERROR
                result.exit_code = result.exit_code or 1
                result.error += f"\nFailed to collect sandbox artifacts: {exc}"
        return result
    finally:
        await _dispose(runtime, session_id)
