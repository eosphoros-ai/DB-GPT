from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from dbgpt_app.openapi.api_v1.dashboard import api
from dbgpt_app.openapi.api_v1.dashboard.annotation_intents import AnnotationIntentBatch
from dbgpt_app.openapi.api_v1.dashboard.models import DashboardAccessDeniedError
from dbgpt_app.openapi.api_v1.dashboard.query_logic import QueryLogicRequest


def intent_request():
    return AnnotationIntentBatch(
        items=[
            {
                "draft_id": "1",
                "prompt": "解释计算口径",
                "target": {"kind": "widget", "widget_id": "sales", "label": "销售额"},
            }
        ]
    )


@pytest.mark.asyncio
async def test_viewer_cannot_invoke_annotation_routing(monkeypatch):
    monkeypatch.setattr(api, "_user_id", lambda user: "viewer")
    resolver = AsyncMock()
    monkeypatch.setattr(api, "resolve_annotation_intents", resolver)
    service = SimpleNamespace(
        _authorized_entity=Mock(side_effect=DashboardAccessDeniedError("edit required"))
    )
    with pytest.raises(HTTPException) as raised:
        await api.resolve_dashboard_annotation_intents(
            "board", intent_request(), user=None, service=service
        )
    assert raised.value.status_code == 403
    resolver.assert_not_awaited()


@pytest.mark.asyncio
async def test_authentication_failure_is_not_reported_as_a_model_failure(monkeypatch):
    def unauthenticated(_user):
        raise HTTPException(status_code=401)

    monkeypatch.setattr(api, "_user_id", unauthenticated)
    with pytest.raises(HTTPException) as raised:
        await api.resolve_dashboard_annotation_intents(
            "board", intent_request(), user=None, service=Mock()
        )
    assert raised.value.status_code == 401


def test_sql_explanation_does_not_connect_to_an_unrelated_data_source(monkeypatch):
    monkeypatch.setattr(api, "_user_id", lambda user: "viewer")
    get_connector = Mock()
    service = SimpleNamespace(
        _authorized_entity=Mock(),
        get_dashboard=Mock(
            return_value=SimpleNamespace(
                schema_payload=SimpleNamespace(
                    dashboard=SimpleNamespace(data_source_id="allowed"),
                    widgets=[],
                )
            )
        ),
        query_executor=SimpleNamespace(_get_connector=get_connector),
    )
    with pytest.raises(HTTPException) as raised:
        api.get_dashboard_query_logic(
            "board",
            QueryLogicRequest(sql="SELECT 1", data_source_id="other"),
            user=None,
            service=service,
        )
    assert raised.value.status_code == 422
    get_connector.assert_not_called()
