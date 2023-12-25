from typing import List

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
    return ServeConfig()


@pytest.fixture
def dao(server_config):
    return ServeDao(server_config)


@pytest.fixture
def default_entity_dict():
    return {
        "chat_scene": "chat_data",
        "sub_chat_scene": "excel",
        "prompt_type": "common",
        "prompt_name": "my_prompt_1",
        "content": "Write a qsort function in python.",
        "user_name": "zhangsan",
        "sys_code": "dbgpt",
        "prompt_language": "zh",
        "model": "vicuna-13b-v1.5",
    }


def test_table_exist():
    assert ServeEntity.__tablename__ in db.metadata.tables


def test_entity_create(default_entity_dict):
    entity: ServeEntity = ServeEntity.create(**default_entity_dict)
    with db.session() as session:
        db_entity: ServeEntity = session.query(ServeEntity).get(entity.id)
        assert db_entity.id == entity.id
        assert db_entity.chat_scene == "chat_data"
        assert db_entity.sub_chat_scene == "excel"
        assert db_entity.prompt_type == "common"
        assert db_entity.prompt_name == "my_prompt_1"
        assert db_entity.content == "Write a qsort function in python."
        assert db_entity.user_name == "zhangsan"
        assert db_entity.sys_code == "dbgpt"
        assert db_entity.gmt_created is not None
        assert db_entity.gmt_modified is not None


def test_entity_unique_key(default_entity_dict):
    ServeEntity.create(**default_entity_dict)
    with pytest.raises(Exception):
        ServeEntity.create(
            **{
                "prompt_name": "my_prompt_1",
                "sys_code": "dbgpt",
                "prompt_language": "zh",
                "model": "vicuna-13b-v1.5",
            }
        )


def test_entity_get(default_entity_dict):
    entity: ServeEntity = ServeEntity.create(**default_entity_dict)
    db_entity: ServeEntity = ServeEntity.get(entity.id)
    assert db_entity.id == entity.id
    assert db_entity.chat_scene == "chat_data"
    assert db_entity.sub_chat_scene == "excel"
    assert db_entity.prompt_type == "common"
    assert db_entity.prompt_name == "my_prompt_1"
    assert db_entity.content == "Write a qsort function in python."
    assert db_entity.user_name == "zhangsan"
    assert db_entity.sys_code == "dbgpt"
    assert db_entity.gmt_created is not None
    assert db_entity.gmt_modified is not None


def test_entity_update(default_entity_dict):
    entity: ServeEntity = ServeEntity.create(**default_entity_dict)
    entity.update(prompt_name="my_prompt_2")
    db_entity: ServeEntity = ServeEntity.get(entity.id)
    assert db_entity.id == entity.id
    assert db_entity.chat_scene == "chat_data"
    assert db_entity.sub_chat_scene == "excel"
    assert db_entity.prompt_type == "common"
    assert db_entity.prompt_name == "my_prompt_2"
    assert db_entity.content == "Write a qsort function in python."
    assert db_entity.user_name == "zhangsan"
    assert db_entity.sys_code == "dbgpt"
    assert db_entity.gmt_created is not None
    assert db_entity.gmt_modified is not None


def test_entity_delete(default_entity_dict):
    entity: ServeEntity = ServeEntity.create(**default_entity_dict)
    entity.delete()
    db_entity: ServeEntity = ServeEntity.get(entity.id)
    assert db_entity is None


def test_entity_all():
    for i in range(10):
        ServeEntity.create(
            chat_scene="chat_data",
            sub_chat_scene="excel",
            prompt_type="common",
            prompt_name=f"my_prompt_{i}",
            content="Write a qsort function in python.",
            user_name="zhangsan",
            sys_code="dbgpt",
        )
    entities = ServeEntity.all()
    assert len(entities) == 10
    for entity in entities:
        assert entity.chat_scene == "chat_data"
        assert entity.sub_chat_scene == "excel"
        assert entity.prompt_type == "common"
        assert entity.content == "Write a qsort function in python."
        assert entity.user_name == "zhangsan"
        assert entity.sys_code == "dbgpt"
        assert entity.gmt_created is not None
        assert entity.gmt_modified is not None


def test_dao_create(dao, default_entity_dict):
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)
    assert res is not None
    assert res.id == 1
    assert res.chat_scene == "chat_data"
    assert res.sub_chat_scene == "excel"
    assert res.prompt_type == "common"
    assert res.prompt_name == "my_prompt_1"
    assert res.content == "Write a qsort function in python."
    assert res.user_name == "zhangsan"
    assert res.sys_code == "dbgpt"


def test_dao_get_one(dao, default_entity_dict):
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)
    res: ServerResponse = dao.get_one(
        {"prompt_name": "my_prompt_1", "sys_code": "dbgpt"}
    )
    assert res is not None
    assert res.id == 1
    assert res.chat_scene == "chat_data"
    assert res.sub_chat_scene == "excel"
    assert res.prompt_type == "common"
    assert res.prompt_name == "my_prompt_1"
    assert res.content == "Write a qsort function in python."
    assert res.user_name == "zhangsan"
    assert res.sys_code == "dbgpt"


def test_get_dao_get_list(dao):
    for i in range(10):
        dao.create(
            ServeRequest(
                chat_scene="chat_data",
                sub_chat_scene="excel",
                prompt_type="common",
                prompt_name=f"my_prompt_{i}",
                content="Write a qsort function in python.",
                user_name="zhangsan" if i % 2 == 0 else "lisi",
                sys_code="dbgpt",
            )
        )
    res: List[ServerResponse] = dao.get_list({"sys_code": "dbgpt"})
    assert len(res) == 10
    for i, r in enumerate(res):
        assert r.id == i + 1
        assert r.chat_scene == "chat_data"
        assert r.sub_chat_scene == "excel"
        assert r.prompt_type == "common"
        assert r.prompt_name == f"my_prompt_{i}"
        assert r.content == "Write a qsort function in python."
        assert r.user_name == "zhangsan" if i % 2 == 0 else "lisi"
        assert r.sys_code == "dbgpt"

    half_res: List[ServerResponse] = dao.get_list({"user_name": "zhangsan"})
    assert len(half_res) == 5


def test_dao_update(dao, default_entity_dict):
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)
    res: ServerResponse = dao.update(
        {"prompt_name": "my_prompt_1", "sys_code": "dbgpt"},
        ServeRequest(prompt_name="my_prompt_2"),
    )
    assert res is not None
    assert res.id == 1
    assert res.chat_scene == "chat_data"
    assert res.sub_chat_scene == "excel"
    assert res.prompt_type == "common"
    assert res.prompt_name == "my_prompt_2"
    assert res.content == "Write a qsort function in python."
    assert res.user_name == "zhangsan"
    assert res.sys_code == "dbgpt"


def test_dao_delete(dao, default_entity_dict):
    req = ServeRequest(**default_entity_dict)
    res: ServerResponse = dao.create(req)
    dao.delete({"prompt_name": "my_prompt_1", "sys_code": "dbgpt"})
    res: ServerResponse = dao.get_one(
        {"prompt_name": "my_prompt_1", "sys_code": "dbgpt"}
    )
    assert res is None


def test_dao_get_list_page(dao):
    for i in range(20):
        dao.create(
            ServeRequest(
                chat_scene="chat_data",
                sub_chat_scene="excel",
                prompt_type="common",
                prompt_name=f"my_prompt_{i}",
                content="Write a qsort function in python.",
                user_name="zhangsan" if i % 2 == 0 else "lisi",
                sys_code="dbgpt",
            )
        )
    res = dao.get_list_page({"sys_code": "dbgpt"}, page=1, page_size=8)
    assert res.total_count == 20
    assert res.total_pages == 3
    assert res.page == 1
    assert res.page_size == 8
    assert len(res.items) == 8
    for i, r in enumerate(res.items):
        assert r.id == i + 1
        assert r.chat_scene == "chat_data"
        assert r.sub_chat_scene == "excel"
        assert r.prompt_type == "common"
        assert r.prompt_name == f"my_prompt_{i}"
        assert r.content == "Write a qsort function in python."
        assert r.user_name == "zhangsan" if i % 2 == 0 else "lisi"
        assert r.sys_code == "dbgpt"

    res_half = dao.get_list_page({"user_name": "zhangsan"}, page=2, page_size=8)
    assert res_half.total_count == 10
    assert res_half.total_pages == 2
    assert res_half.page == 2
    assert res_half.page_size == 8
    assert len(res_half.items) == 2
    for i, r in enumerate(res_half.items):
        assert r.chat_scene == "chat_data"
        assert r.sub_chat_scene == "excel"
        assert r.prompt_type == "common"
        assert r.content == "Write a qsort function in python."
        assert r.user_name == "zhangsan"
        assert r.sys_code == "dbgpt"
