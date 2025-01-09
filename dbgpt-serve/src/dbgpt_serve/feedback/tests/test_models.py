import pytest

from dbgpt.storage.metadata import db

from ..api.schemas import ServeRequest, ServerResponse
from ..config import ServeConfig
from ..models.models import ServeDao, ServeEntity


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()

    yield


@pytest.fixture
def server_config():
    # TODO : build your server config
    return ServeConfig()


@pytest.fixture
def dao(server_config):
    return ServeDao(server_config)


@pytest.fixture
def default_entity_dict():
    # TODO: build your default entity dict
    return {}


def test_table_exist():
    assert ServeEntity.__tablename__ in db.metadata.tables


def test_entity_create(default_entity_dict):
    with db.session() as session:
        entity = ServeEntity(**default_entity_dict)
        session.add(entity)


def test_entity_unique_key(default_entity_dict):
    # TODO: implement your test case
    pass


def test_entity_get(default_entity_dict):
    # TODO: implement your test case
    pass


def test_entity_update(default_entity_dict):
    # TODO: implement your test case
    pass


def test_entity_delete(default_entity_dict):
    # TODO: implement your test case
    pass


def test_entity_all():
    # TODO: implement your test case
    pass


def test_dao_create(dao, default_entity_dict):
    # TODO: implement your test case
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)
    assert res is not None


def test_dao_get_one(dao, default_entity_dict):
    # TODO: implement your test case
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)


def test_get_dao_get_list(dao):
    # TODO: implement your test case
    pass


def test_dao_update(dao, default_entity_dict):
    # TODO: implement your test case
    pass


def test_dao_delete(dao, default_entity_dict):
    # TODO: implement your test case
    pass


def test_dao_get_list_page(dao):
    # TODO: implement your test case
    pass


# Add more test cases according to your own logic
