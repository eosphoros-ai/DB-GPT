"""``AppConfig.get_all_by_prefix`` must reflect writes made through ``set``.

It is decorated with ``functools.cache``, which keys on ``(self, prefix)`` and
never expires, so the first call freezes a snapshot: later ``set()`` writes are
invisible to it, while ``get()`` on the same instance sees them. The cached dict
is also the object handed back, so a caller that mutates the result changes what
every later caller sees.
"""

from dbgpt.util.config_utils import AppConfig


def test_prefix_view_reflects_a_new_key():
    config = AppConfig({"app.name": "dbgpt"})

    assert config.get_all_by_prefix("app.") == {"app.name": "dbgpt"}

    config.set("app.version", "1.0")

    assert config.get("app.version") == "1.0"
    assert config.get_all_by_prefix("app.") == {
        "app.name": "dbgpt",
        "app.version": "1.0",
    }


def test_prefix_view_reflects_an_overwrite():
    config = AppConfig({"app.name": "dbgpt"})
    config.get_all_by_prefix("app.")

    config.set("app.name", "renamed", overwrite=True)

    assert config.get_all_by_prefix("app.") == {"app.name": "renamed"}


def test_prefix_view_returns_an_independent_dict():
    config = AppConfig({"app.name": "dbgpt"})

    first = config.get_all_by_prefix("app.")
    first["app.injected"] = True

    assert "app.injected" not in config.get_all_by_prefix("app.")
