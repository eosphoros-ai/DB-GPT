"""Regression tests for issue #3104: the python file-upload endpoint must not
let an untrusted ``user_id`` header escape the uploads directory via path
traversal.

Suggested location in the repo:
    packages/dbgpt-app/tests/openapi/test_python_upload_path_traversal.py

Run (from the repo, with dev deps installed):
    pytest packages/dbgpt-app/tests/openapi/test_python_upload_path_traversal.py -v
"""
import os

import pytest

from dbgpt_app.openapi.api_v1.python_upload_api import _resolve_upload_dir


def test_traversal_user_id_is_rejected():
    with pytest.raises(ValueError):
        _resolve_upload_dir("/srv/work", "../../../../../../tmp/DBGPT_PWN")


@pytest.mark.parametrize("bad", ["..", "/etc", "a/b", "../evil", "../../etc/cron.d"])
def test_unsafe_user_ids_are_rejected(bad):
    with pytest.raises(ValueError):
        _resolve_upload_dir("/srv/work", bad)


@pytest.mark.parametrize("good", ["default", "admin", "user_42", "3f2b-uuid", "user@example.com"])
def test_legit_user_ids_stay_inside_uploads_root(tmp_path, good):
    uploads_root = os.path.realpath(os.path.join(str(tmp_path), "python_uploads"))
    resolved = os.path.realpath(_resolve_upload_dir(str(tmp_path), good))
    assert resolved.startswith(uploads_root + os.sep)
    # the user_id is preserved as the leaf directory name
    assert os.path.basename(resolved) == good
