import inspect
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from dbgpt_app.openapi.api_v1.dashboard import api

from .test_api import _schema

OPERATIONS = (
    ("features", "template_features"),
    ("source", "inspect_source"),
    ("preview", "preview_template"),
    ("adapt", "adapt_template"),
    ("generate", "instantiate_template"),
    ("generate-adapted", "create_adapted_template"),
)


async def invoke(operation, template_id):
    if operation == "features":
        result = api.inspect_catalog_features(template_id)
    elif operation == "source":
        result = api.inspect_catalog_source(
            template_id, "test", user=None, service=None
        )
    elif operation == "adapt":
        result = api.adapt_catalog_dashboard(
            template_id,
            api.TemplateAdaptRequest(data_source_id="test"),
            user=None,
            service=None,
        )
    else:
        request = api.CatalogGenerateRequest(
            data_source_id="test",
            schema=_schema() if operation == "generate-adapted" else None,
        )
        handler = (
            api.preview_catalog_dashboard
            if operation == "preview"
            else api.generate_catalog_dashboard
        )
        result = handler(template_id, request, user=None, service=None)
    return await result if inspect.isawaitable(result) else result


@pytest.mark.asyncio
@pytest.mark.parametrize("operation,target", OPERATIONS)
@pytest.mark.parametrize(
    "template_id", ["store-coverage", "unknown", "brutal-viz-design"]
)
async def test_catalog_rejects_removed_ids_before_queries_or_model_calls(
    monkeypatch, operation, target, template_id
):
    operation_mock = AsyncMock() if operation == "adapt" else Mock()
    monkeypatch.setattr(api, target, operation_mock)
    with pytest.raises(HTTPException) as raised:
        await invoke(operation, template_id)
    assert raised.value.status_code == 404
    operation_mock.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation,target", OPERATIONS)
async def test_catalog_keeps_retained_template_routes(monkeypatch, operation, target):
    operation_mock = (
        AsyncMock(return_value={"retained": True})
        if operation == "adapt"
        else Mock(return_value={"retained": True})
    )
    monkeypatch.setattr(api, target, operation_mock)
    monkeypatch.setattr(api, "_user_id", lambda _: "alice")
    result = await invoke(operation, "retail-overview")
    assert result.success and result.data == {"retained": True}
    operation_mock.assert_called_once()


@pytest.mark.parametrize(
    "template_id",
    [
        "voice-observatory",
        "store-marketing",
        "national-command",
        "brand-revenue",
        "northwind-revenue",
        "retail-overview",
    ],
)
def test_each_retained_catalog_template_has_features(template_id):
    result = api.inspect_catalog_features(template_id)
    assert result.success and result.data["template_id"] == template_id
