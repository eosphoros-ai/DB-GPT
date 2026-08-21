"""Tests for the session-file aware file tools.

load_file returns public file metadata plus the per-turn materialized
path (so the model can analyze files with code_interpreter without
guessing); execute_analysis and code_interpreter pass file locations to
subprocesses through the environment. Internal handoff details
(``files_json_path``) and storage URIs/hashes never appear in chunks.
"""

import json
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.tools import code_interpreter as code_interpreter_module
from dbgpt_app.openapi.api_v1.tools import execute_analysis as execute_analysis_module
from dbgpt_app.openapi.api_v1.tools import load_file as load_file_module
from dbgpt_serve.session_file.domain import SessionFileManifest, SessionFileStatus

OWNER_CSV = b"region,sales\nwest,1\n"
HOSTILE_NAME = 'qu"ote\\back\nslash;$(touch escaped).csv'


def _manifest(
    file_id,
    name,
    *,
    kind="table",
    media="text/csv",
    size=len(OWNER_CSV),
    status=SessionFileStatus.READY,
    ordinal=0,
):
    return SessionFileManifest(
        file_id=file_id,
        name=name,
        size=size,
        media_type=media,
        kind=kind,
        status=status,
        ordinal=ordinal,
    )


def _write_materialized(tmp_path, index, file_id, content=OWNER_CSV):
    path = tmp_path / f"materialized_{index}.csv"
    path.write_bytes(content)
    return str(path)


def _session_state(tmp_path, entries):
    """Build react state whose internal data lives only in env inputs."""
    manifests = []
    inspections = {}
    mapping = {}
    for index, entry in enumerate(entries):
        file_id, name, preview, truncated = entry
        path = _write_materialized(tmp_path, index, file_id)
        manifests.append(_manifest(file_id, name, ordinal=index))
        inspections[file_id] = {"preview": preview, "truncated": truncated}
        mapping[file_id] = path
    files_json = tmp_path / "files.json"
    files_json.write_text(json.dumps(mapping), encoding="utf-8")
    local_paths = list(mapping.values())
    return {
        "session_files": manifests,
        "session_file_inspections": inspections,
        "session_file_paths": dict(mapping),
        "file_path": local_paths[0],
        "files_json_path": str(files_json),
        "conv_id": "conv-test",
    }


def _chunks(result):
    return json.loads(result)["chunks"]


def _text(chunks):
    return "\n".join(
        chunk["content"]
        for chunk in chunks
        if chunk.get("output_type") == "text" and isinstance(chunk.get("content"), str)
    )


def _json_chunks(chunks):
    return [chunk["content"] for chunk in chunks if chunk.get("output_type") == "json"]


# ---------------------------------------------------------------------------
# load_file: bounded public observations, subsets and no path disclosure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("react_state", [{}, {"file_path": None}])
def test_load_file_text_only_output_is_unchanged(react_state):
    tool = load_file_module.make_load_file(react_state)

    result = tool()

    assert json.loads(result) == {
        "chunks": [{"output_type": "text", "content": "No file uploaded"}]
    }


def test_load_file_legacy_file_reports_name_and_current_path(tmp_path):
    target = _write_materialized(tmp_path, 0, "sf_legacy")
    tool = load_file_module.make_load_file({"file_path": target})

    chunks = _chunks(tool())

    payload = json.dumps(chunks, ensure_ascii=False)
    assert target in payload
    assert Path(target).name in payload
    assert "File provided by user upload" in payload


def test_load_file_without_session_files_rejects_id_selection(tmp_path):
    target = _write_materialized(tmp_path, 0, "sf_legacy")
    tool = load_file_module.make_load_file({"file_path": target})

    chunks = _chunks(tool(file_ids=["sf_a"]))

    assert "not found" in _text(chunks).lower()
    payload = json.dumps(chunks, ensure_ascii=False)
    assert target not in payload
    assert str(tmp_path) not in payload


def test_load_file_no_args_summarizes_selected_session_files(tmp_path):
    state = _session_state(
        tmp_path,
        [
            (
                "sf_alpha",
                "sales.csv",
                {"rows": [["region", "sales"], ["west", "1"]]},
                False,
            ),
            (
                "sf_beta",
                "notes.txt",
                {"text": "quarterly planning notes"},
                True,
            ),
        ],
    )
    tool = load_file_module.make_load_file(state)

    chunks = _chunks(tool())

    assert all(chunk["output_type"] == "text" for chunk in chunks)
    content = "\n".join(chunk["content"] for chunk in chunks)
    for expected in (
        "sf_alpha",
        "sf_beta",
        "sales.csv",
        "notes.txt",
        "ready",
        "region",
        "sales",
        "truncated",
        "file_id",
        "valid for this turn only",
    ):
        assert expected in content
    payload = json.dumps(chunks, ensure_ascii=False)
    # Materialized per-turn paths are surfaced so the model can analyze the
    # files directly with code_interpreter.
    for path in state["session_file_paths"].values():
        assert path in payload
    # The internal child-process handoff file stays invisible.
    assert state["files_json_path"] not in payload


def test_load_file_exact_subset_is_bounded_with_notice(tmp_path, monkeypatch):
    entries = [
        (f"sf_{index}", f"file_{index}.csv", {"rows": [["n"], [index]]}, False)
        for index in range(5)
    ]
    state = _session_state(tmp_path, entries)
    monkeypatch.setattr(load_file_module, "MAX_LOAD_FILE_FILES", 2)
    tool = load_file_module.make_load_file(state)

    chunks = _chunks(tool(file_ids=[f"sf_{index}" for index in range(5)]))

    content = "\n".join(chunk["content"] for chunk in chunks)
    assert "sf_0" in content
    assert "sf_1" in content
    assert "sf_2" not in content
    assert "3 more file(s) not shown" in content
    # Only the shown files' paths surface.
    assert state["session_file_paths"]["sf_0"] in content
    assert state["session_file_paths"]["sf_1"] in content
    assert state["session_file_paths"]["sf_2"] not in content


def test_load_file_observation_chars_are_capped_with_notice(tmp_path, monkeypatch):
    entries = [
        (
            f"sf_{index}",
            f"file_{index}.csv",
            {"text": f"detail-{index} " + ("x" * 100)},
            False,
        )
        for index in range(6)
    ]
    state = _session_state(tmp_path, entries)
    monkeypatch.setattr(load_file_module, "MAX_LOAD_FILE_CHARS", 140)
    tool = load_file_module.make_load_file(state)

    chunks = _chunks(tool())

    assert len(chunks) == 1
    content = chunks[0]["content"]
    assert len(content) <= 250  # cap plus guide and the truncation notice
    assert "truncated" in content
    assert str(tmp_path) not in content


@pytest.mark.parametrize(
    "file_ids", [[], ["sf_a", "sf_a"], ["sf_a", 7], ["sf_a", ""], "sf_a"]
)
def test_load_file_malformed_selection_returns_error(tmp_path, file_ids):
    state = _session_state(
        tmp_path,
        [("sf_a", "a.csv", {"rows": [["a"], ["1"]]}, False)],
    )
    tool = load_file_module.make_load_file(state)

    chunks = _chunks(tool(file_ids=file_ids))

    assert json.loads(json.dumps(chunks))
    assert "invalid" in _text(chunks).lower()
    assert str(tmp_path) not in json.dumps(chunks, ensure_ascii=False)


# ---------------------------------------------------------------------------
# execute_analysis: subset validation, env propagation and partial failures
# ---------------------------------------------------------------------------


def _patch_analysis_runner(monkeypatch, tmp_path, stdout_payload, returncode=0):
    class Seam:
        calls = []

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.calls.append(
                {
                    "code": Path(script_path).read_text(encoding="utf-8"),
                    "cwd": cwd,
                    "env": dict(env),
                    "timeout": timeout,
                }
            )
            return returncode, stdout_payload.encode("utf-8"), b""

    seam = Seam()
    monkeypatch.setattr(execute_analysis_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot"),
    )
    return seam


@pytest.mark.asyncio
async def test_execute_analysis_text_only_output_is_unchanged():
    tool = execute_analysis_module.make_execute_analysis({})

    result = await tool()

    assert json.loads(result) == {
        "chunks": [{"output_type": "text", "content": "No file to analyze"}]
    }


@pytest.mark.asyncio
async def test_execute_analysis_legacy_env_propagates_path_without_code_interpolation(
    tmp_path, monkeypatch
):
    hostile_path = _write_materialized(tmp_path, 0, HOSTILE_NAME)
    seamless_stdout = json.dumps(
        {
            "files": [
                {
                    "file_id": "file",
                    "name": Path(hostile_path).name,
                    "shape": [2, 2],
                    "columns": ["region", "sales"],
                    "dtypes": {"region": "object", "sales": "int64"},
                    "head": [{"region": "west", "sales": 1}],
                }
            ]
        }
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, seamless_stdout)
    tool = execute_analysis_module.make_execute_analysis({"file_path": hostile_path})

    chunks = _chunks(await tool())

    assert [chunk["output_type"] for chunk in chunks] == [
        "code",
        "json",
        "table",
        "chart",
    ]
    assert len(seam.calls) == 1
    call = seam.calls[0]
    assert call["env"]["FILE_PATH"] == hostile_path
    assert call["env"]["ANALYZE_IDS"] == json.dumps(["file"])
    assert "hostname" not in call["cwd"]
    assert call["cwd"].startswith(str(tmp_path))
    assert hostile_path not in call["code"]
    assert HOSTILE_NAME not in call["code"]
    assert "os.environ" in call["code"]
    assert "; touch" not in call["code"]
    payload = json.dumps(chunks, ensure_ascii=False)
    assert hostile_path not in payload
    assert str(tmp_path) not in payload
    assert [chunk["output_type"] for chunk in chunks[:3]] == [
        "code",
        "json",
        "table",
    ]


@pytest.mark.asyncio
async def test_execute_analysis_no_args_uses_all_session_files_through_env(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [
            ("sf_alpha", HOSTILE_NAME, {"rows": [["a", "b"], ["1", "2"]]}, False),
            ("sf_beta", "b.csv", {"rows": [["x"], ["3"]]}, False),
        ],
    )
    mapping = json.loads(Path(state["files_json_path"]).read_text())
    stdout_payload = json.dumps(
        {
            "files": [
                {
                    "file_id": "sf_alpha",
                    "name": HOSTILE_NAME,
                    "shape": [2, 2],
                    "columns": ["a", "b"],
                    "dtypes": {"a": "int64", "b": "int64"},
                    "head": [{"a": 1, "b": 2}],
                },
                {
                    "file_id": "sf_beta",
                    "name": "b.csv",
                    "shape": [1, 1],
                    "columns": ["x"],
                    "dtypes": {"x": "int64"},
                    "head": [{"x": 3}],
                },
            ]
        }
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, stdout_payload)
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool())

    assert [chunk["output_type"] for chunk in chunks[:2]] == ["code", "json"]
    assert len(seam.calls) == 1
    call = seam.calls[0]
    assert call["env"]["FILE_PATH"] == mapping["sf_alpha"]
    assert call["env"]["FILES_JSON"] == state["files_json_path"]
    assert json.loads(call["env"]["ANALYZE_IDS"]) == ["sf_alpha", "sf_beta"]
    assert json.loads(call["env"]["ANALYZE_NAMES"]) == {
        "sf_alpha": HOSTILE_NAME,
        "sf_beta": "b.csv",
    }
    code = call["code"]
    assert "os.environ" in code
    assert state["files_json_path"] not in code
    assert mapping["sf_alpha"] not in code
    assert mapping["sf_beta"] not in code
    assert HOSTILE_NAME not in code
    assert str(tmp_path) not in code
    payload = json.dumps(chunks, ensure_ascii=False)
    assert state["file_path"] not in payload
    assert state["files_json_path"] not in payload
    assert mapping["sf_alpha"] not in payload
    assert mapping["sf_beta"] not in payload
    assert "sf_alpha" in payload and "sf_beta" in payload


@pytest.mark.asyncio
async def test_execute_analysis_exact_subset_is_validated_in_request_order(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [
            ("sf_alpha", "a.csv", {"rows": [["a"], ["1"]]}, False),
            ("sf_beta", "b.csv", {"rows": [["b"], ["2"]]}, False),
            ("sf_gamma", "c.csv", {"rows": [["c"], ["3"]]}, False),
        ],
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, '{"files": []}')
    tool = execute_analysis_module.make_execute_analysis(state)

    await tool(file_ids=["sf_gamma", "sf_alpha"])

    call = seam.calls[0]
    assert json.loads(call["env"]["ANALYZE_IDS"]) == ["sf_gamma", "sf_alpha"]
    assert json.loads(call["env"]["ANALYZE_NAMES"]) == {
        "sf_gamma": "c.csv",
        "sf_alpha": "a.csv",
    }
    assert call["env"]["FILE_PATH"] == state["file_path"]
    assert call["env"]["FILES_JSON"] == state["files_json_path"]
    assert str(tmp_path) not in call["code"]


@pytest.mark.asyncio
async def test_execute_analysis_mixed_unknown_and_valid_ids_is_partial_success(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [("sf_alpha", "a.csv", {"rows": [["a"], ["1"]]}, False)],
    )
    stdout_payload = json.dumps(
        {
            "files": [
                {
                    "file_id": "sf_alpha",
                    "name": "a.csv",
                    "shape": [1, 1],
                    "columns": ["a"],
                    "dtypes": {"a": "int64"},
                    "head": [{"a": 1}],
                }
            ]
        }
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, stdout_payload)
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool(file_ids=["sf_alpha", "sf_foreign"]))

    assert json.loads(seam.calls[0]["env"]["ANALYZE_IDS"]) == ["sf_alpha"]
    text = _text(chunks)
    assert "sf_foreign" in text
    assert "not found" in text.lower()
    assert _json_chunks(chunks)[0]["file_id"] == "sf_alpha"
    assert str(tmp_path) not in text


@pytest.mark.asyncio
@pytest.mark.parametrize("file_ids", [["sf_foreign"], [], ["sf_a", 3]])
async def test_execute_analysis_foreign_or_malformed_selection_never_executes(
    tmp_path, monkeypatch, file_ids
):
    state = _session_state(
        tmp_path,
        [("sf_a", "a.csv", {"rows": [["a"], ["1"]]}, False)],
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, '{"files": []}')
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool(file_ids=file_ids))

    assert seam.calls == []
    text = _text(chunks)
    assert "No analyzable files" in text or "invalid" in text.lower()
    payload = json.dumps(chunks, ensure_ascii=False)
    assert state["file_path"] not in payload
    assert state["files_json_path"] not in payload


@pytest.mark.asyncio
async def test_execute_analysis_partial_file_failure_is_visible_as_error_chunk(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [
            ("sf_good", "good.csv", {"rows": [["a"], ["1"]]}, False),
            ("sf_bad", "bad.csv", {"rows": [["b"], ["2"]]}, False),
        ],
    )
    local_map = json.loads(Path(state["files_json_path"]).read_text())
    stdout_payload = json.dumps(
        {
            "files": [
                {
                    "file_id": "sf_good",
                    "name": "good.csv",
                    "shape": [1, 1],
                    "columns": ["a"],
                    "dtypes": {"a": "int64"},
                    "head": [{"a": 1}],
                },
                {
                    "file_id": "sf_bad",
                    "name": "bad.csv",
                    "error": f"ParserError: {local_map['sf_bad']} is broken",
                },
            ]
        }
    )
    _patch_analysis_runner(monkeypatch, tmp_path, stdout_payload)
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool())

    assert _json_chunks(chunks)[0]["file_id"] == "sf_good"
    text = _text(chunks)
    assert "bad.csv" in text
    assert "analysis failed" in text
    payload = json.dumps(chunks, ensure_ascii=False)
    assert local_map["sf_bad"] not in payload
    assert local_map["sf_good"] not in payload
    assert state["files_json_path"] not in payload


@pytest.mark.asyncio
async def test_execute_analysis_zero_analyzable_files_is_only_hard_failure(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [
            ("sf_bad1", "bad1.csv", {"rows": [["a"], ["1"]]}, False),
            ("sf_bad2", "bad2.csv", {"rows": [["b"], ["2"]]}, False),
        ],
    )
    stdout_payload = json.dumps(
        {
            "files": [
                {
                    "file_id": "sf_bad1",
                    "name": "bad1.csv",
                    "error": "ParserError: broken",
                },
                {
                    "file_id": "sf_bad2",
                    "name": "bad2.csv",
                    "error": "ParserError: broken",
                },
            ]
        }
    )
    seam = _patch_analysis_runner(monkeypatch, tmp_path, stdout_payload)
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool())

    assert len(seam.calls) == 1
    text = _text(chunks)
    assert "No analyzable files" in text
    assert "bad1.csv analysis failed" in text
    assert "bad2.csv analysis failed" in text
    assert not _json_chunks(chunks)
    assert str(tmp_path) not in json.dumps(chunks, ensure_ascii=False)


# ---------------------------------------------------------------------------
# code_interpreter: the execution boundary carries paths only in env
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_code_interpreter_propagates_file_context_only_through_env(
    tmp_path, monkeypatch
):
    hostile_path = _write_materialized(tmp_path, 0, "unsafe")
    files_json = tmp_path / "files.json"
    files_json.write_text(json.dumps({"sf_evil": hostile_path}), encoding="utf-8")
    state = {
        "conv_id": "conv-env",
        "file_path": hostile_path,
        "files_json_path": str(files_json),
    }

    class Seam:
        calls = []

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.calls.append(
                {
                    "code": Path(script_path).read_text(encoding="utf-8"),
                    "cwd": cwd,
                    "env": dict(env),
                    "timeout": timeout,
                }
            )
            return 0, b"env-ok\n", b""

    seam = Seam()
    monkeypatch.setattr(code_interpreter_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot-root"),
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.STATIC_MESSAGE_IMG_PATH",
        str(tmp_path / "static-images"),
    )
    tool = code_interpreter_module.make_code_interpreter(state)

    chunks = _chunks(await tool(code="print('env boundary')"))

    assert len(seam.calls) == 1
    call = seam.calls[0]
    assert call["env"]["FILE_PATH"] == hostile_path
    assert call["env"]["FILES_JSON"] == str(files_json)
    assert call["env"]["PLOT_DIR"] == call["cwd"]
    assert call["cwd"].startswith(str(tmp_path))
    code = call["code"]
    assert "os.environ" in code
    assert hostile_path not in code
    assert str(files_json) not in code
    assert str(tmp_path) not in code
    assert 'FILE_PATH = r"' not in code
    assert 'FILES_JSON = r"' not in code
    assert chunks[0] == {"output_type": "code", "content": "print('env boundary')"}
    assert {"output_type": "text", "content": "env-ok"} in chunks
    payload = json.dumps(chunks, ensure_ascii=False)
    assert hostile_path not in payload
    assert str(files_json) not in payload
    assert str(tmp_path) not in payload


@pytest.mark.asyncio
async def test_code_interpreter_without_files_uses_env_for_plot_dir_only(
    tmp_path, monkeypatch
):
    class Seam:
        calls = []

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.calls.append(
                {
                    "code": Path(script_path).read_text(encoding="utf-8"),
                    "cwd": cwd,
                    "env": dict(env),
                }
            )
            return 0, b"plain\n", b""

    seam = Seam()
    monkeypatch.setattr(code_interpreter_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot-root"),
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.STATIC_MESSAGE_IMG_PATH",
        str(tmp_path / "static-images"),
    )
    tool = code_interpreter_module.make_code_interpreter({"conv_id": "plain-conv"})

    chunks = _chunks(await tool(code="print(42)"))

    call = seam.calls[0]
    assert call["env"]["PLOT_DIR"] == call["cwd"]
    assert "FILE_PATH" not in call["env"]
    assert "FILES_JSON" not in call["env"]
    assert call["cwd"] not in call["code"]
    assert "os.environ" in call["code"]
    assert chunks[0] == {"output_type": "code", "content": "print(42)"}
    assert {"output_type": "text", "content": "plain"} in chunks


# ---------------------------------------------------------------------------
# code_interpreter: a timed-out run reports the timeout, never "(no output)"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_code_interpreter_timeout_surfaces_timeout_message(tmp_path, monkeypatch):
    class Seam:
        calls = []

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.calls.append({"cwd": cwd, "timeout": timeout})
            return None, b"", b""

    seam = Seam()
    monkeypatch.setattr(code_interpreter_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot-root"),
    )
    monkeypatch.setattr(
        "dbgpt.configs.model_config.STATIC_MESSAGE_IMG_PATH",
        str(tmp_path / "static-images"),
    )
    tool = code_interpreter_module.make_code_interpreter({"conv_id": "conv-timeout"})

    chunks = _chunks(await tool(code="while True: pass"))

    assert len(seam.calls) == 1
    text = _text(chunks)
    assert "Execution timed out (60s limit)" in text
    assert "(no output" not in text
    assert str(tmp_path) not in json.dumps(chunks, ensure_ascii=False)


# ---------------------------------------------------------------------------
# execute_analysis: conv_id is a single strict-allowlist path component, and
# failure messages scrub the runner script path / work dir (and thus the id)
# ---------------------------------------------------------------------------


async def _run_analysis_direct(state, **overrides):
    kwargs = {
        "react_state": state,
        "analyze_ids": ["file"],
        "analyze_names": {"file": "a.csv"},
        "files_json_path": None,
    }
    kwargs.update(overrides)
    return await execute_analysis_module._run_analysis(**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_cid",
    [
        "../../escape",
        "sub/dir",
        "back\\slash",
        "nul\x00byte",
        ".",
        "..",
        ".hidden",
        "CON",
        "x" * 300,
        "中文会话",
    ],
)
async def test_run_analysis_rejects_unsafe_conv_id(tmp_path, monkeypatch, bad_cid):
    seam = _patch_analysis_runner(monkeypatch, tmp_path, '{"files": []}')

    files, failure = await _run_analysis_direct({"conv_id": bad_cid})

    assert files == []
    assert "invalid" in failure.lower()
    assert seam.calls == []


@pytest.mark.asyncio
async def test_run_analysis_traversal_conv_id_cannot_escape_tmp_root(
    tmp_path, monkeypatch
):
    seam = _patch_analysis_runner(monkeypatch, tmp_path, '{"files": []}')

    files, failure = await _run_analysis_direct({"conv_id": "../../escape"})

    assert files == []
    assert "invalid" in failure.lower()
    assert seam.calls == []
    assert not (tmp_path / "escape").exists()
    pilot_root = tmp_path / "pilot"
    if pilot_root.exists():
        for path in pilot_root.rglob("*"):
            assert path.relative_to(pilot_root).parts[0] == "tmp"


@pytest.mark.asyncio
async def test_run_analysis_accepts_simple_allowlist_conv_id(tmp_path, monkeypatch):
    _patch_analysis_runner(monkeypatch, tmp_path, '{"files": []}')

    for cid in ("conv-test", "CON1", "a.b_c~d=e-1"):
        files, failure = await _run_analysis_direct({"conv_id": cid})

        assert files == []
        assert failure == "", f"cid {cid!r} must stay valid: {failure}"


@pytest.mark.asyncio
async def test_execute_analysis_failure_scrubs_runner_paths_and_conv_id(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [("sf_a", "a.csv", {"rows": [["a"], ["1"]]}, False)],
    )

    class Seam:
        script_path = ""
        cwd = ""

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.script_path = script_path
            self.cwd = cwd
            stderr = (
                "Traceback (most recent call last):\n"
                f'  File "{script_path}", line 60, in <module>\n'
                f"    raise RuntimeError('boom from {cwd}')\n"
                f"RuntimeError: boom from {cwd}\n"
            )
            return 1, b"", stderr.encode("utf-8")

    seam = Seam()
    monkeypatch.setattr(execute_analysis_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot"),
    )
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool())

    text = _text(chunks)
    assert "Analysis failed" in text
    assert "RuntimeError: boom from <file>" in text
    payload = json.dumps(chunks, ensure_ascii=False)
    for leaked in (
        seam.script_path,
        seam.cwd,
        str(tmp_path),
        "conv-test",
        "_analysis_",
    ):
        assert leaked not in payload, f"leaked: {leaked}"


@pytest.mark.asyncio
async def test_execute_analysis_zero_json_failure_scrubs_runner_paths(
    tmp_path, monkeypatch
):
    state = _session_state(
        tmp_path,
        [("sf_a", "a.csv", {"rows": [["a"], ["1"]]}, False)],
    )

    class Seam:
        script_path = ""

        async def __call__(self, script_path, *, cwd, env, timeout=60):
            self.script_path = script_path
            return 0, f"preamble {script_path}\nnot-a-json-line".encode("utf-8"), b""

    seam = Seam()
    monkeypatch.setattr(execute_analysis_module, "_run_python_file", seam)
    monkeypatch.setattr(
        "dbgpt.configs.model_config.PILOT_PATH",
        str(tmp_path / "pilot"),
    )
    tool = execute_analysis_module.make_execute_analysis(state)

    chunks = _chunks(await tool())

    text = _text(chunks)
    assert "Analysis failed" in text
    assert "not-a-json-line" in text
    payload = json.dumps(chunks, ensure_ascii=False)
    for leaked in (seam.script_path, str(tmp_path), "conv-test", "_analysis_"):
        assert leaked not in payload, f"leaked: {leaked}"
