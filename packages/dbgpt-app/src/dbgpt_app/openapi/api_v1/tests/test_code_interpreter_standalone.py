"""Regression for the standard agent image, which does not install DB-GPT.

Build ``packages/dbgpt-sandbox/src/docker_images/Dockerfile.agent`` as
``dbgpt-sandbox-agent:latest`` and set ``DBGPT_TEST_DOCKER=1`` to also run the
same generated scripts in real Docker containers. Without opt-in, isolated Python
children explicitly reject all DB-GPT imports to exercise the image contract.
"""

import asyncio
import inspect
import io
import json
import os
import sys
import tarfile
from pathlib import Path

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_sql_execution,
    read_artifact_result,
)
from dbgpt_app.openapi.api_v1.tools import code_interpreter as interpreter


@pytest.fixture(params=["isolated", "docker"])
def sandbox(request, monkeypatch, tmp_path):
    from dbgpt.configs import model_config

    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path))
    if request.param == "docker":
        if os.getenv("DBGPT_TEST_DOCKER") != "1":
            pytest.skip("Set DBGPT_TEST_DOCKER=1 with the standard image built")
        import docker
        from dbgpt_sandbox.sandbox.config import SANDBOX_AGENT_IMAGE

        async def run_in_image(script_path, *, cwd, env, timeout):
            # Archive transfer keeps this image regression runnable from Windows
            # as well as Linux without bind-mounting the host checkout or store.
            client = docker.from_env(timeout=timeout)
            container = None
            try:
                container = client.containers.run(
                    SANDBOX_AGENT_IMAGE, detach=True, working_dir="/workspace"
                )
                with io.BytesIO() as archive:
                    with tarfile.open(fileobj=archive, mode="w") as tar:
                        for path in Path(cwd).iterdir():
                            tar.add(path, arcname=path.name)
                    archive.seek(0)
                    assert container.put_archive("/workspace", archive.getvalue())
                environment = {
                    key: (
                        "/workspace"
                        if value == cwd
                        else "/workspace/" + Path(value).relative_to(cwd).as_posix()
                        if value and Path(value).is_relative_to(Path(cwd))
                        else value
                    )
                    for key, value in env.items()
                }
                check = container.exec_run(
                    [
                        "python",
                        "-c",
                        "import importlib.util; "
                        "assert importlib.util.find_spec('dbgpt') is None",
                    ]
                )
                assert check.exit_code == 0, check.output
                result = container.exec_run(
                    ["python", "-I", Path(script_path).relative_to(cwd).as_posix()],
                    environment=environment,
                    workdir="/workspace",
                    demux=True,
                )
                stream, _ = container.get_archive("/workspace")
                with tarfile.open(fileobj=io.BytesIO(b"".join(stream))) as tar:
                    for key in ("REPORT_RESULT_PATH", "SQL_INPUT_TRACE_PATH"):
                        host_path = Path(env[key])
                        name = host_path.relative_to(cwd).as_posix()
                        try:
                            source = tar.extractfile("workspace/" + name)
                        except KeyError:
                            continue
                        with source:
                            host_path.parent.mkdir(parents=True, exist_ok=True)
                            host_path.write_bytes(source.read())
                stdout, stderr = result.output
                return result.exit_code, stdout or b"", stderr or b""
            finally:
                if container is not None:
                    container.remove(force=True)
                client.close()

        monkeypatch.setattr(interpreter, "_run_python_file", run_in_image)
        return

    async def run_without_dbgpt(script_path, *, cwd, env, timeout):
        # -I removes editable checkout/PYTHONPATH imports; the import hook also
        # rejects DB-GPT if this environment happens to have a wheel installed.
        guard = """
import builtins
_original_import = builtins.__import__
def _without_dbgpt(name, *args, **kwargs):
    if name == 'dbgpt' or name.startswith('dbgpt.'):
        raise ModuleNotFoundError("No module named 'dbgpt'")
    return _original_import(name, *args, **kwargs)
builtins.__import__ = _without_dbgpt
"""
        source = guard + Path(script_path).read_text(encoding="utf-8")
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            "-c",
            source,
            cwd=cwd,
            env={**os.environ, **env},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), timeout)
        except asyncio.TimeoutError:
            child.kill()
            await child.communicate()
            raise
        return child.returncode, stdout, stderr

    monkeypatch.setattr(interpreter, "_run_python_file", run_without_dbgpt)


async def execute(state, code):
    tool = inspect.unwrap(interpreter.make_code_interpreter(state))
    return json.loads(await tool(code=code))


@pytest.mark.asyncio
async def test_plain_python_without_report_or_sql_context(sandbox):
    response = await execute({}, "print(6 * 7)")
    assert any(chunk.get("content") == "42" for chunk in response["chunks"])
    assert not any("ModuleNotFoundError" in str(c) for c in response["chunks"])


@pytest.mark.asyncio
async def test_report_result_normalization_without_dbgpt(sandbox):
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="standalone-result"))
    response = await execute(
        {"conv_id": "standalone-result", "_report_artifact_sink": sink},
        "from decimal import Decimal\n"
        "from datetime import date\n"
        "REPORT_RESULT = {'amount': Decimal('12.30'), 'day': date(2026, 10, 18),\n"
        "                 'scalar': np.int64(7), 'missing': pd.NA,\n"
        "                 'nonfinite': float('nan')}\nprint('captured')",
    )
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == response["artifact_id"]
    )
    assert artifact.status == "succeeded", artifact.error
    assert read_artifact_result(artifact) == {
        "amount": {"$decimal": "12.30"},
        "day": {"$date": "2026-10-18"},
        "scalar": 7,
        "missing": None,
        "nonfinite": {"$number": "NaN"},
    }


@pytest.mark.asyncio
async def test_complete_sql_snapshot_and_actual_input_lineage(sandbox):
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="standalone-sql"))
    used_id = capture_sql_execution(
        sql="SELECT sales FROM test",
        database="test",
        columns=["sales"],
        rows=[{"sales": value} for value in range(1200)],
        duration_ms=1,
        artifact_sink=sink,
    )
    unused_id = capture_sql_execution(
        sql="SELECT 99 AS unused",
        database="test",
        columns=["unused"],
        rows=[{"unused": 99}],
        duration_ms=1,
        artifact_sink=sink,
    )
    # The first SQL artifact exceeds the inline preview limit. Its full blob
    # must be transferred, never fetched from the host store by sandbox code.
    assert sink.snapshot()[0].result.inline["truncated"]
    response = await execute(
        {"conv_id": "standalone-sql", "_report_artifact_sink": sink},
        "frame = sql_result_frame(0)\n"
        "REPORT_RESULT = {'rows': len(frame), 'sum': int(frame.sales.sum())}",
    )
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == response["artifact_id"]
    )
    assert artifact.status == "succeeded", artifact.error
    assert read_artifact_result(artifact) == {"rows": 1200, "sum": sum(range(1200))}
    assert used_id in artifact.input_artifact_ids
    assert unused_id not in artifact.input_artifact_ids
