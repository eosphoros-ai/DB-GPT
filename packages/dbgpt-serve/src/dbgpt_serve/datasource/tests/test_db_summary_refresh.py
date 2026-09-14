"""Regression tests for non-blocking datasource refresh."""

from unittest.mock import MagicMock

from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient


def test_delete_db_profile_returns_false_when_indexing_is_in_progress(monkeypatch):
    lock = MagicMock()
    lock.acquire.return_value = False
    monkeypatch.setattr(
        "dbgpt_serve.datasource.service.db_summary_client._get_db_index_lock",
        lambda dbname: lock,
    )

    client = object.__new__(DBSummaryClient)

    assert client.delete_db_profile("mssql_db") is False
    lock.acquire.assert_called_once_with(blocking=False)


def test_delete_db_profile_releases_lock_after_delete(monkeypatch):
    lock = MagicMock()
    lock.acquire.return_value = True
    table_store = MagicMock()
    field_store = MagicMock()
    storage_manager = MagicMock()
    storage_manager.create_vector_store.side_effect = [table_store, field_store]
    system_app = MagicMock()
    client = object.__new__(DBSummaryClient)
    client.system_app = system_app

    monkeypatch.setattr(
        "dbgpt_serve.datasource.service.db_summary_client._get_db_index_lock",
        lambda dbname: lock,
    )
    monkeypatch.setattr(
        "dbgpt_serve.datasource.service.db_summary_client.StorageManager.get_instance",
        lambda app: storage_manager,
    )

    assert client.delete_db_profile("mssql_db") is True
    table_store.delete_vector_name.assert_called_once_with("mssql_db_profile")
    field_store.delete_vector_name.assert_called_once_with("mssql_db_profile_field")
    lock.release.assert_called_once_with()
