import pytest

from dbgpt_app.openapi.api_v1.editor.api_editor_v1 import (
    chart_run,
    editor_sql_run,
    resolve_editor_db_name,
)
from dbgpt_app.openapi.api_v1.editor.service import nonempty_db_name


def test_nonempty_db_name_skips_whitespace_before_fallback():
    assert nonempty_db_name("   ", "Walmart_Sales") == "Walmart_Sales"
    assert nonempty_db_name(None, "  orders  ") == "orders"
    assert nonempty_db_name("   ", None, "") == ""


def test_resolve_editor_db_name_from_request():
    assert resolve_editor_db_name({"db_name": " sales "}) == "sales"


def test_resolve_editor_db_name_skips_blank():
    assert resolve_editor_db_name({"db_name": "  "}) is None
    assert resolve_editor_db_name({}) is None


def test_resolve_editor_db_name_from_conversation():
    class _Conv:
        param_value = "walmart"
        messages = []

    class _Service:
        def get_storage_conv(self, conv_uid: str):
            assert conv_uid == "c1"
            return _Conv()

    assert (
        resolve_editor_db_name({"con_uid": "c1"}, editor_service=_Service())
        == "walmart"
    )


def test_resolve_editor_db_name_from_message_kwargs():
    class _Msg:
        additional_kwargs = {"param_value": "orders"}

    class _Conv:
        param_value = ""
        messages = [_Msg()]

    class _Service:
        def get_storage_conv(self, conv_uid: str):
            return _Conv()

    assert (
        resolve_editor_db_name({"conv_uid": "c2"}, editor_service=_Service())
        == "orders"
    )


class _NoDbService:
    def get_storage_conv(self, conv_uid: str):
        raise RuntimeError("should not load conversation without conv uid")


@pytest.mark.asyncio
async def test_chart_run_missing_db_name_returns_failed_result():
    result = await chart_run(
        {"sql": "select 1", "chart_type": "bar"},
        editor_service=_NoDbService(),
    )
    assert result.success is False
    assert "db_name" in (result.err_msg or "")


@pytest.mark.asyncio
async def test_editor_sql_run_missing_db_name_returns_failed_result():
    result = await editor_sql_run(
        {"sql": "select 1"},
        editor_service=_NoDbService(),
    )
    assert result.success is False
    assert "db_name" in (result.err_msg or "")
