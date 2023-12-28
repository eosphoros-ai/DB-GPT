from typing import List

import pytest

from dbgpt.component import SystemApp
from dbgpt.serve.core.tests.conftest import system_app
from dbgpt.storage.metadata import db

from ..api.schemas import ServeRequest, ServerResponse
from ..models.models import ServeEntity
from ..service.service import Service


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest.fixture
def service(system_app: SystemApp):
    instance = Service(system_app)
    instance.init_app(system_app)
    return instance


@pytest.fixture
def default_entity_dict():
    # TODO: build your default entity dict
    return {}


@pytest.mark.parametrize(
    "system_app",
    [{"app_config": {"DEBUG": True, "dbgpt.serve.test_key": "hello"}}],
    indirect=True,
)
def test_config_exists(service: Service):
    system_app: SystemApp = service._system_app
    assert system_app.config.get("DEBUG") is True
    assert system_app.config.get("dbgpt.serve.test_key") == "hello"
    assert service.config is not None


def test_service_create(service: Service, default_entity_dict):
    # TODO: implement your test case
    # eg. entity: ServerResponse = service.create(ServeRequest(**default_entity_dict))
    # ...
    pass


def test_service_update(service: Service, default_entity_dict):
    # TODO: implement your test case
    pass


def test_service_get(service: Service, default_entity_dict):
    # TODO: implement your test case
    pass


def test_service_delete(service: Service, default_entity_dict):
    # TODO: implement your test case
    pass


def test_service_get_list(service: Service):
    # TODO: implement your test case
    pass


def test_service_get_list_by_page(service: Service):
    # TODO: implement your test case
    pass


# Add more test cases according to your own logic
