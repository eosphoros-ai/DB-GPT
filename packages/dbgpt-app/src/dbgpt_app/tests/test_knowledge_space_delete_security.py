"""Path-traversal regression tests for /knowledge/space/delete.

Locks the fix for a directory-traversal flaw where a space name of ".."
resolved the deletion target to the parent of the upload root
(<repo>/pilot), recursively wiping the metadata DB, vector stores and all
uploaded files — while the endpoint still reported a failure.

Locked behaviors:

1. Names that are not plain single path components (".", "..", names
   containing path separators or NUL, empty/None) are rejected without
   touching the filesystem and without consulting the knowledge service.
2. A name that passes the format check but matches no existing space fails
   inside ``delete_space`` *before* any filesystem deletion — even when a
   directory with that name exists under the upload root.
3. The resolved target must stay inside the upload root: a symlinked
   per-space directory pointing outside the root is never followed.
4. A valid space still deletes its own upload directory as before.
"""

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dbgpt_app.knowledge.api as knowledge_api


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Fake data root: upload_root/<space>, parent dir holding meta_data."""
    pilot_root = tmp_path / "pilot"
    upload_root = pilot_root / "data"
    upload_root.mkdir(parents=True)
    (upload_root / "keep.txt").write_text("keep")
    (pilot_root / "meta_data").mkdir()
    (pilot_root / "meta_data" / "dbgpt.db").write_text("db")

    monkeypatch.setattr(knowledge_api, "KNOWLEDGE_UPLOAD_ROOT_PATH", str(upload_root))
    service = Mock()
    monkeypatch.setattr(knowledge_api, "knowledge_space_service", service)

    app = FastAPI()
    app.include_router(knowledge_api.router)
    return TestClient(app), service, upload_root, pilot_root


def _post(client, name):
    return client.post("/knowledge/space/delete", json={"name": name}).json()


@pytest.mark.parametrize(
    "name", ["..", ".", "a/../b", "/abs/path", "..\\win", "a\\b", "", None]
)
def test_traversal_names_rejected_without_any_side_effect(env, name):
    client, service, upload_root, pilot_root = env

    body = _post(client, name)

    assert body["success"] is False
    assert "invalid space name" in body["err_msg"]
    service.delete_space.assert_not_called()
    # The parent of the upload root (the real data root) is untouched.
    assert (pilot_root / "meta_data" / "dbgpt.db").exists()
    assert (upload_root / "keep.txt").exists()


def test_unknown_space_fails_before_filesystem_deletion(env):
    """The historic bug deleted the directory first and only then reported
    'invalid space name'. The directory must survive a failed delete."""
    client, service, upload_root, pilot_root = env
    decoy = upload_root / "no_such_space"
    decoy.mkdir()
    (decoy / "marker.txt").write_text("x")
    service.delete_space.side_effect = Exception("invalid space name:no_such_space")

    body = _post(client, "no_such_space")

    assert body["success"] is False
    assert "invalid space name:no_such_space" in body["err_msg"]
    service.delete_space.assert_called_once_with("no_such_space")
    assert (decoy / "marker.txt").exists()
    assert (pilot_root / "meta_data" / "dbgpt.db").exists()


def test_symlinked_space_dir_pointing_outside_is_not_followed(env, tmp_path):
    client, service, upload_root, pilot_root = env
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (upload_root / "linked_space").symlink_to(outside, target_is_directory=True)

    body = _post(client, "linked_space")

    assert body["success"] is False
    assert "invalid space name" in body["err_msg"]
    service.delete_space.assert_not_called()
    assert (outside / "secret.txt").exists()


def test_valid_space_deletes_own_upload_dir(env):
    client, service, upload_root, pilot_root = env
    space_dir = upload_root / "real_space"
    space_dir.mkdir()
    (space_dir / "doc.txt").write_text("doc")
    service.delete_space.return_value = 1

    body = _post(client, "real_space")

    assert body["success"] is True
    service.delete_space.assert_called_once_with("real_space")
    assert not space_dir.exists()
    assert (upload_root / "keep.txt").exists()


def test_valid_space_without_upload_dir_still_succeeds(env):
    """Newer spaces have no per-space upload directory; deletion must work."""
    client, service, upload_root, _ = env
    service.delete_space.return_value = 1

    body = _post(client, "dirless_space")

    assert body["success"] is True
    service.delete_space.assert_called_once_with("dirless_space")
