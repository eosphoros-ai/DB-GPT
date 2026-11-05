import pytest

from dbgpt_app.openapi.api_v1.editor.api_editor_v1 import (
    chart_run,
    editor_sql_run,
    get_editor_tables,
    resolve_editor_db_name,
)
from dbgpt_app.openapi.api_v1.editor.service import EditorService, nonempty_db_name


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


class _NoConnectorManager:
    def get_connector(self, db_name: str):
        raise AssertionError(f"connector for hidden datasource {db_name!r} opened")


@pytest.fixture
def no_connector(monkeypatch):
    from dbgpt_app.openapi.api_v1.editor import api_editor_v1

    class _Cfg:
        local_db_manager = _NoConnectorManager()

    monkeypatch.setattr(api_editor_v1, "CFG", _Cfg())


@pytest.mark.asyncio
@pytest.mark.parametrize("db_name", ["dbgpt", "DBGPT", "dbgpt ", "auth"])
async def test_editor_sql_run_rejects_hidden_datasource(no_connector, db_name):
    result = await editor_sql_run(
        {"db_name": db_name, "sql": "select 1"},
        editor_service=_NoDbService(),
    )
    assert result.success is False
    assert "not available" in (result.err_msg or "")


@pytest.mark.asyncio
async def test_chart_run_rejects_hidden_datasource(no_connector):
    result = await chart_run(
        {"db_name": "dbgpt", "sql": "select 1", "chart_type": "bar"},
        editor_service=_NoDbService(),
    )
    assert result.success is False
    assert "not available" in (result.err_msg or "")


@pytest.mark.asyncio
async def test_get_editor_tables_rejects_hidden_datasource(no_connector):
    result = await get_editor_tables("dbgpt", page_index=1, page_size=10)
    assert result.success is False
    assert "not available" in (result.err_msg or "")


class _HiddenParamConvService:
    """Conversation whose stored ``param_value`` names a hidden datasource."""

    def get_storage_conv(self, conv_uid: str):
        class _Conv:
            param_value = "dbgpt"
            messages = []

        return _Conv()


class _HiddenMessageConvService:
    """Conversation whose message ``additional_kwargs`` name a hidden datasource."""

    def get_storage_conv(self, conv_uid: str):
        class _Msg:
            additional_kwargs = {"param_value": "DBGPT"}

        class _Conv:
            param_value = ""
            messages = [_Msg()]

        return _Conv()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "service", [_HiddenParamConvService(), _HiddenMessageConvService()]
)
@pytest.mark.parametrize("route", [editor_sql_run, chart_run])
async def test_editor_rejects_hidden_datasource_from_conversation(
    no_connector, route, service
):
    result = await route(
        {"conv_uid": "c1", "sql": "select 1", "chart_type": "bar"},
        editor_service=service,
    )
    assert result.success is False
    assert "not available" in (result.err_msg or "")


def test_get_editor_chart_info_rejects_hidden_datasource():
    class _ViewMsg:
        round_index = 1
        type = "view"
        additional_kwargs = {"param_value": "dbgpt"}
        content = "{}"

    class _Conv:
        param_value = ""
        messages = [_ViewMsg()]

    class _Service:
        def get_storage_conv(self, conv_uid: str):
            return _Conv()

    class _Cfg:
        local_db_manager = _NoConnectorManager()

    result = EditorService.get_editor_chart_info(_Service(), "c1", "chart", _Cfg())
    assert result.success is False
    assert "not available" in (result.err_msg or "")
