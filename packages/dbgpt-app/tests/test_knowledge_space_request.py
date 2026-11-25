"""Regression tests for the knowledge space request schema.

The knowledge CLI posts the whole ``KnowledgeSpaceRequest`` model, including
the fields the user never touched (``ApiClient._post`` serialises
``request.__dict__``).  ``KnowledgeSpaceRequest.desc`` was declared as a
required ``str`` while its default was ``None``, so every CLI call that did
not set a description sent ``"desc": null`` and the API rejected the request
body with ``body.desc: Input should be a valid string`` (HTTP 400).  That
made ``dbgpt knowledge delete`` (and ``dbgpt knowledge list``) unusable.
"""

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt_app.knowledge._cli.knowledge_client import KnowledgeApiClient
from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest

CLI_URL = "http://localhost:5670/api"


@pytest.fixture()
def client() -> TestClient:
    """A minimal app mirroring the knowledge space endpoints.

    FastAPI validates the request body with the very same model the real
    router uses, so this reproduces the API side of the bug.
    """
    app = FastAPI()

    @app.post("/knowledge/space/list")
    def space_list(request: KnowledgeSpaceRequest):
        return {"name": request.name}

    @app.post("/knowledge/space/delete")
    def space_delete(request: KnowledgeSpaceRequest):
        return {"name": request.name}

    return TestClient(app)


def _capture_cli_payload(call) -> dict:
    """Run a CLI call and return the JSON body that would be sent."""
    with patch("dbgpt_app.knowledge._cli.knowledge_client.requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "success": True,
            "err_code": None,
            "err_msg": None,
            "data": [],
        }
        call()
        return json.loads(post.call_args.kwargs["data"])


def test_space_request_desc_is_optional():
    """`desc` is not required, so it must not be typed as a mandatory str."""
    request = KnowledgeSpaceRequest(name="my_space")
    assert request.desc is None


def test_cli_space_list_payload_is_accepted_by_the_api(client):
    """`dbgpt knowledge list` sends the whole model, including `desc: null`."""
    payload = _capture_cli_payload(
        lambda: KnowledgeApiClient(CLI_URL).space_list(
            KnowledgeSpaceRequest(name="my_space")
        )
    )
    assert payload["desc"] is None

    response = client.post("/knowledge/space/list", json=payload)
    assert response.status_code == 200, response.text


def test_cli_space_delete_payload_is_accepted_by_the_api(client):
    """`dbgpt knowledge delete` sends the whole model, including `desc: null`."""
    payload = _capture_cli_payload(
        lambda: KnowledgeApiClient(CLI_URL).space_delete(
            KnowledgeSpaceRequest(name="my_space")
        )
    )
    assert payload["desc"] is None

    response = client.post("/knowledge/space/delete", json=payload)
    assert response.status_code == 200, response.text
