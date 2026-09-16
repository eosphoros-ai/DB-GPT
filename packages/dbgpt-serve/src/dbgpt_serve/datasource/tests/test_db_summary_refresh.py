"""Regression tests for non-blocking datasource refresh."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient
from dbgpt_serve.datasource.service.service import Service


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


def test_service_delete_rejects_when_profile_delete_cannot_acquire_lock():
    service = object.__new__(Service)
    service._dao = MagicMock()
    service._dao.get_one.return_value = SimpleNamespace(db_name="mssql_db")
    service._db_summary_client = MagicMock()
    service._db_summary_client.delete_db_profile.return_value = False

    with pytest.raises(HTTPException) as error:
        service.delete("42")

    assert error.value.status_code == 409
    service._dao.delete.assert_not_called()


def test_service_refresh_is_noop_when_profile_delete_cannot_acquire_lock(
    monkeypatch,
):
    service = object.__new__(Service)
    service._dao = MagicMock()
    service._dao.get_one.return_value = SimpleNamespace(
        db_name="mssql_db", db_type="mssql"
    )
    service._db_summary_client = MagicMock()
    service._db_summary_client.delete_db_profile.return_value = False
    connector_manager = MagicMock()
    monkeypatch.setattr(
        Service,
        "datasource_manager",
        property(lambda _service: connector_manager),
    )
    service._system_app = MagicMock()

    assert service.refresh("42") is True

    connector_manager.invalidate_connector.assert_not_called()
    service._system_app.get_component.assert_not_called()
