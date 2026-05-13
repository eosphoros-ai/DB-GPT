from dbgpt.agent.resource.connector.manager import ConnectorManager
from dbgpt.component import SystemApp

from dbgpt_app.component_configs import _initialize_connector_manager


def test_initialize_connector_manager_registers_manager_and_loads_catalog():
    system_app = SystemApp()

    _initialize_connector_manager(system_app)

    manager = system_app.get_component("connector_manager", ConnectorManager)

    assert manager._catalog.get("github") is not None
    assert manager._catalog.get("github").display_name == "GitHub"
