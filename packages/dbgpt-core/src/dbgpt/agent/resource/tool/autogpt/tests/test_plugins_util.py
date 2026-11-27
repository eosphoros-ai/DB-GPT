from unittest.mock import MagicMock, patch

import pytest

from dbgpt.agent.resource.tool.autogpt.plugins_util import (
    _validate_branch_name,
    _validate_download_url,
    _validate_github_repo_url,
    update_from_git,
)


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1:8163/github.com",
        "http://github.com/owner/repo",
        "https://evil.com/github.com/owner/repo",
        "https://github.com.evil.com/owner/repo",
        "https://github.com@evil.com/owner/repo",
        "https://github.com:8443/owner/repo",
        "https://github.com/only-owner",
        "https://github.com/owner/repo/extra",
        "https://github.com/owner/repo?foo=bar",
        "https://github.com/../repo",
        "https://github.com/owner/..git",
    ],
)
def test_validate_github_repo_url_rejects_untrusted_inputs(bad_url):
    with pytest.raises(ValueError):
        _validate_github_repo_url(bad_url)


def test_validate_github_repo_url_canonicalizes_valid_repo():
    url, repo = _validate_github_repo_url("https://github.com/owner/my.repo.git/")
    assert url == "https://github.com/owner/my.repo"
    assert repo == "my.repo"


def test_ssrf_url_does_not_issue_http_request(tmp_path):
    with (
        patch("requests.Session") as mock_session,
        patch("requests.get") as mock_get,
    ):
        with pytest.raises(ValueError):
            update_from_git(
                str(tmp_path),
                github_repo="http://127.0.0.1:8163/github.com",
                branch_name="main",
                authorization="Bearer secret",
            )
    mock_session.assert_not_called()
    mock_get.assert_not_called()


def test_validate_branch_name_allows_plus_character(tmp_path):
    assert _validate_branch_name("release+hotfix") == "release+hotfix"

    ok_resp = MagicMock(
        status_code=200, is_redirect=False, content=b"PK\x05\x06" + b"\x00" * 18
    )
    session_instance = MagicMock()
    session_instance.get.return_value = ok_resp

    with patch("requests.Session", return_value=session_instance):
        repo_name = update_from_git(
            str(tmp_path),
            github_repo="https://github.com/owner/repo",
            branch_name="release+hotfix",
        )

    assert repo_name == "repo"
    session_instance.get.assert_called_once()
    assert (
        session_instance.get.call_args.args[0]
        == "https://github.com/owner/repo/archive/refs/heads/release+hotfix.zip"
    )
    assert list(tmp_path.glob("repo-release+hotfix-*.zip"))


@pytest.mark.parametrize(
    "bad_branch",
    ["../evil", "main/../../evil", "main?foo=bar", "main#frag", "main with spaces"],
)
def test_update_from_git_rejects_invalid_branch(tmp_path, bad_branch):
    with pytest.raises(ValueError):
        update_from_git(
            str(tmp_path),
            github_repo="https://github.com/owner/repo",
            branch_name=bad_branch,
        )


def test_redirect_to_non_github_host_is_blocked(tmp_path):
    redirect_resp = MagicMock(
        status_code=302,
        is_redirect=True,
        headers={"Location": "http://127.0.0.1/evil.zip"},
    )
    session_instance = MagicMock()
    session_instance.get.return_value = redirect_resp

    with patch("requests.Session", return_value=session_instance):
        with pytest.raises(ValueError, match="download plugin exception"):
            update_from_git(
                str(tmp_path),
                github_repo="https://github.com/owner/repo",
                branch_name="main",
            )
    assert session_instance.get.call_count == 1


def test_redirect_to_codeload_strips_authorization_header(tmp_path):
    redirect_resp = MagicMock(
        status_code=302,
        is_redirect=True,
        headers={
            "Location": "https://codeload.github.com/owner/repo/zip/refs/heads/main"
        },
    )
    ok_resp = MagicMock(
        status_code=200, is_redirect=False, content=b"PK\x05\x06" + b"\x00" * 18
    )
    session_instance = MagicMock()
    session_instance.get.side_effect = [redirect_resp, ok_resp]

    with patch("requests.Session", return_value=session_instance):
        repo_name = update_from_git(
            str(tmp_path),
            github_repo="https://github.com/owner/repo",
            branch_name="main",
            authorization="Bearer secret",
        )

    assert repo_name == "repo"
    assert session_instance.get.call_count == 2
    first_call = session_instance.get.call_args_list[0]
    second_call = session_instance.get.call_args_list[1]
    assert first_call.kwargs["headers"] == {"Authorization": "Bearer secret"}
    assert first_call.kwargs["allow_redirects"] is False
    assert first_call.kwargs["timeout"] == 30
    assert second_call.kwargs["headers"] == {}
    assert list(tmp_path.glob("repo-main-*.zip"))


def test_validate_download_url_rejects_ip_and_custom_port():
    with pytest.raises(ValueError):
        _validate_download_url("https://127.0.0.1/owner/repo.zip")
    with pytest.raises(ValueError):
        _validate_download_url("https://github.com:8443/owner/repo.zip")
