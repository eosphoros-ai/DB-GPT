"""Filename traversal regression tests for flow package import.

Locks the fix for _parse_flow_from_zip_file interpolating the multipart
filename verbatim into os.path.join(temp_dir, filename): an absolute-path
filename discarded the temp dir and wrote attacker bytes anywhere the
service account could write — before any package validation ran.

Locked behaviors:
1. Absolute-path and ".." filenames are confined to the temp dir: nothing
   is written outside it, whatever the filename carries.
2. Invalid/missing filenames are rejected before any file write.
3. A normal filename keeps working unchanged.
"""

import asyncio
import io
import os
import tempfile
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from dbgpt_serve.flow.service import share_utils
from dbgpt_serve.flow.service.share_utils import _parse_flow_from_zip_file


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("flow.json", "{}")
    return buf.getvalue()


def _upload(filename) -> UploadFile:
    return UploadFile(file=io.BytesIO(_zip_bytes()), filename=filename)


@pytest.fixture(autouse=True)
def _isolate_from_system_app(monkeypatch):
    """Run the loader synchronously with a stub; avoids SystemApp setup and
    makes the observed zip_path the only thing the parser sees."""
    import dbgpt.util.dbgpts.loader as loader

    async def run_sync(sys_app, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(share_utils, "blocking_func_to_async", run_sync)
    monkeypatch.setattr(
        loader,
        "_load_flow_package_from_zip_path",
        lambda path: SimpleNamespace(zip_path=path),
    )


def _run(file: UploadFile):
    return asyncio.run(_parse_flow_from_zip_file(file, None))


def test_absolute_path_filename_is_confined_to_temp_dir(tmp_path):
    decoy = tmp_path / "escape_poc.zip"
    assert not decoy.exists()

    result = _run(_upload(str(decoy)))

    assert not decoy.exists()
    assert result.zip_path.startswith(tempfile.gettempdir())
    assert result.zip_path.endswith("escape_poc.zip")


def test_dotdot_filename_is_confined_to_temp_dir(tmp_path):
    decoy = tmp_path / "escape_poc_dotdot.zip"
    result = _run(_upload(f"../{tmp_path.name}/escape_poc_dotdot.zip"))

    assert not decoy.exists()
    assert result.zip_path.startswith(tempfile.gettempdir())


def test_windows_style_filename_is_confined(tmp_path):
    result = _run(_upload("..\\..\\evil_flow.zip"))
    assert result.zip_path.startswith(tempfile.gettempdir())
    assert (tmp_path / "evil_flow.zip").exists() is False


@pytest.mark.parametrize("filename", [None, "", "no_ext", "flow.txt", ".."])
def test_invalid_filenames_rejected_before_any_write(filename):
    with pytest.raises(ValueError):
        _run(_upload(filename))


def test_normal_filename_unchanged():
    result = _run(_upload("我的 flow v2.zip"))
    assert result.zip_path.endswith(os.path.join("", "我的 flow v2.zip"))
    assert result.zip_path.startswith(tempfile.gettempdir())
