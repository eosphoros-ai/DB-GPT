"""Native uploads retain original contents and reject invalid packages."""

import asyncio
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, UploadFile

from dbgpt_serve.plugins.api.endpoints import upload_suite

from .test_loader import write_plugin


def upload(payload, service):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            upload_suite(
                file=UploadFile(filename="native.zip", file=io.BytesIO(payload)),
                user_name="test",
                service=service,
            )
        )
    finally:
        loop.close()


def archive(root, prefix="", extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as zf:
        for path in root.rglob("*"):
            if path.is_file():
                zf.writestr(
                    prefix + path.relative_to(root).as_posix(), path.read_bytes()
                )
        if extra:
            zf.writestr(*extra)
    return stream.getvalue()


@pytest.fixture
def native_upload(tmp_path):
    source = write_plugin(tmp_path / "source")
    installed = tmp_path / "installed"
    installed.mkdir()
    service = SimpleNamespace(
        config=SimpleNamespace(suites_dir=str(installed)),
        install_package=Mock(return_value=None),
    )
    return source, installed, service


@pytest.mark.parametrize("prefix", ["", "native/"])
def test_native_upload_accepts_root_or_single_directory(native_upload, prefix):
    source, installed, service = native_upload
    upload(archive(source, prefix), service)
    package = service.install_package.call_args.args[0]
    assert package.name == "native"
    for path in source.rglob("*"):
        if path.is_file():
            assert (installed / "native" / path.relative_to(source)).read_bytes() == (
                path.read_bytes()
            )
    assert not (installed / "native/suite.yaml").exists()


@pytest.mark.parametrize(
    "extra",
    [("../outside.md", "escape"), ("../installed-other/file.md", "escape")],
)
def test_native_upload_rejects_traversal_without_installing(native_upload, extra):
    source, installed, service = native_upload
    with pytest.raises(HTTPException) as error:
        upload(archive(source, extra=extra), service)
    assert error.value.status_code == 400
    assert list(installed.iterdir()) == []
    service.install_package.assert_not_called()


def test_invalid_zip_returns_client_error(native_upload):
    _, installed, service = native_upload
    with pytest.raises(HTTPException) as error:
        upload(b"not a zip", service)
    assert error.value.status_code == 400
    assert list(installed.iterdir()) == []


def test_upgrade_removes_stale_files_and_restores_on_registration_error(native_upload):
    source, installed, service = native_upload
    upload(archive(source), service)
    stale = installed / "native/stale.md"
    stale.write_text("old")
    upload(archive(source), service)
    assert not stale.exists()
    original = (installed / "native/skills/doctor/SKILL.md").read_bytes()
    (source / "skills/doctor/SKILL.md").write_text(
        "---\nname: doctor\n---\nnew version"
    )
    service.install_package.side_effect = RuntimeError("registration failed")
    with pytest.raises(RuntimeError, match="registration failed"):
        upload(archive(source), service)
    assert (installed / "native/skills/doctor/SKILL.md").read_bytes() == original
    assert sorted(path.name for path in installed.iterdir()) == ["native"]
