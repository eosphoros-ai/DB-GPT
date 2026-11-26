from dbgpt.agent.resource.connector.manager import ConnectorManager
from dbgpt.component import SystemApp
from dbgpt_app.component_configs import (
    _initialize_connector_manager,
    _register_specstream_search,
)


def test_initialize_connector_manager_registers_manager_and_loads_catalog():
    system_app = SystemApp()

    _initialize_connector_manager(system_app)

    manager = system_app.get_component("connector_manager", ConnectorManager)

    assert manager._catalog.get("github") is not None
    assert manager._catalog.get("github").display_name == "GitHub"


class _RecordingResourceManager:
    def __init__(self):
        self.registered = []

    def register_resource(self, resource_instance=None, **kwargs):
        self.registered.append(resource_instance)


def test_specstream_search_is_not_registered_without_a_key(monkeypatch):
    monkeypatch.delenv("SPECSTREAM_API_KEY", raising=False)
    rm = _RecordingResourceManager()

    _register_specstream_search(rm)

    assert rm.registered == []


def test_specstream_search_is_registered_with_a_key(monkeypatch):
    from dbgpt.agent.expand.resources.search_tool import specstream_search

    monkeypatch.setenv("SPECSTREAM_API_KEY", "test-key")
    rm = _RecordingResourceManager()

    _register_specstream_search(rm)

    assert rm.registered == [specstream_search]
