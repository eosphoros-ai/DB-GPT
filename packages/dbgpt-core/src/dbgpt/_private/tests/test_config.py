import pytest

from dbgpt._private.config import Config
from dbgpt.util.singleton import Singleton


@pytest.mark.parametrize(
    ("env_value", "expected"),
    [("true", True), ("TRUE", True), ("false", False), ("False", False)],
)
def test_local_db_ssl_verify_parses_boolean_env(monkeypatch, env_value, expected):
    monkeypatch.setenv("LOCAL_DB_SSL_VERIFY", env_value)
    Singleton._instances.pop(Config, None)

    try:
        assert Config().LOCAL_DB_SSL_VERIFY is expected
    finally:
        Singleton._instances.pop(Config, None)
