import importlib.util
import sys
import types
from pathlib import Path

from dbgpt.storage.metadata import db


def _load_connect_config_db_module():
    schemas = types.ModuleType("dbgpt_serve.datasource.api.schemas")

    class DatasourceServeRequest:
        pass

    class DatasourceServeResponse:
        pass

    schemas.DatasourceServeRequest = DatasourceServeRequest
    schemas.DatasourceServeResponse = DatasourceServeResponse
    sys.modules["dbgpt_serve.datasource.api.schemas"] = schemas

    module_path = (
        Path(__file__).resolve().parents[1]
        / "manages"
        / "connect_config_db.py"
    )
    spec = importlib.util.spec_from_file_location(
        "connect_config_db_under_test", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


connect_config_db = _load_connect_config_db_module()
ConnectConfigDao = connect_config_db.ConnectConfigDao


def _new_dao():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    return ConnectConfigDao()


def test_get_db_list_treats_user_id_as_data():
    dao = _new_dao()
    dao.add_file_db("private_db", "sqlite", "/tmp/private.sqlite", user_id="victim")
    dao.add_file_db("public_db", "sqlite", "/tmp/public.sqlite", user_id="")

    rows = dao.get_db_list(user_id="alice' OR 1=1 --")

    assert [row["db_name"] for row in rows] == ["public_db"]


def test_get_db_list_treats_db_name_as_data():
    dao = _new_dao()
    dao.add_file_db("private_db", "sqlite", "/tmp/private.sqlite", user_id="victim")
    dao.add_file_db("public_db", "sqlite", "/tmp/public.sqlite", user_id="")

    rows = dao.get_db_list(db_name="x' OR 1=1 --", user_id="alice")

    assert rows == []


def test_update_db_info_treats_db_name_as_data():
    dao = _new_dao()
    malicious_name = "owned' OR 1=1 --"
    dao.add_file_db("victim_db", "sqlite", "/tmp/victim.sqlite", comment="secret")
    dao.add_file_db(
        malicious_name, "sqlite", "/tmp/owned.sqlite", comment="owned"
    )

    assert dao.update_db_info(
        malicious_name, "sqlite", "/tmp/new.sqlite", comment="pwned"
    )

    comments = {row["db_name"]: row["comment"] for row in dao.get_db_list()}
    assert comments["victim_db"] == "secret"
    assert comments[malicious_name] == "pwned"
