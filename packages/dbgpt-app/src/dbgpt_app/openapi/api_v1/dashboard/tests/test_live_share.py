"""Live sharing must also refresh dashboards without interactive filters."""

# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from dbgpt_app.openapi.api_v1.dashboard.access import DashboardAuthorizationService
from dbgpt_app.openapi.api_v1.dashboard.live_share import (
    DashboardLiveShareEntity,
    LiveShareService,
)
from dbgpt_app.openapi.api_v1.dashboard.models import DashboardAccessDeniedError
from dbgpt_app.openapi.api_v1.dashboard.publication import DashboardPublicationError

from .test_feedback import real_service  # noqa: F401


def unfiltered_record(service, record, *, mixed=False):
    schema = record.schema_payload.model_copy(deep=True)
    schema.filters = []
    widget = schema.widgets[0]
    widget.query.sql = "SELECT SUM(amount) AS value FROM sales"
    widget.query.filter_parameters = {}
    if mixed:
        bound = widget.model_copy(deep=True)
        bound.id = "bound_total"
        bound.publication.filter_fields = {}
        schema.widgets.append(bound)
        layout = schema.layouts.desktop[0].model_copy(deep=True)
        layout.widget_id = bound.id
        layout.y = 4
        schema.layouts.desktop.append(layout)
    widget.publication = None
    return service.update_dashboard(record.id, schema, record.current_revision, "alice")


def expire_cache(service, dashboard_id):
    with service.dao.session() as session:
        session.query(DashboardLiveShareEntity).filter_by(
            dashboard_id=dashboard_id
        ).update({"last_attempt_at": datetime.now() - timedelta(seconds=61)})


@pytest.mark.parametrize("mixed", [False, True], ids=["query-only", "mixed"])
def test_unfiltered_live_share_refreshes_published_queries_and_keeps_snapshot(
    real_service, mixed
):
    service, record, path = real_service
    record = unfiltered_record(service, record, mixed=mixed)
    published = service.publish_dashboard(
        record.id, record.current_revision, {}, "alice"
    )

    # A later draft must never replace the query authorized for the public link.
    draft = record.schema_payload.model_copy(deep=True)
    draft.widgets[0].query.sql = "SELECT 999 AS value"
    service.update_dashboard(record.id, draft, record.current_revision, "alice")
    live = LiveShareService(service)
    token = live.create(record.id, "alice")["share_path"].split("/")[-1]
    first = live.read(token)
    assert first.data_mode == "live"
    assert first.published_revision == published.published_revision
    assert set(first.snapshot.widgets) == {w.id for w in record.schema_payload.widgets}
    assert all(result.rows == [[30.0]] for result in first.snapshot.widgets.values())
    with pytest.raises(
        DashboardPublicationError, match="Unknown public dashboard filters"
    ):
        live.read(token, {"region": "North"})

    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO sales VALUES ('North', 7)")
    assert live.read(token).snapshot.widgets["total"].rows == [[30.0]]
    expire_cache(service, record.id)
    fresh = live.read(token)
    assert not fresh.stale
    assert all(result.rows == [[37.0]] for result in fresh.snapshot.widgets.values())
    assert fresh.snapshot.refreshed_at > first.snapshot.refreshed_at
    assert service.get_public_snapshot(published.share_token).snapshot.widgets[
        "total"
    ].rows == [[30.0]]


def test_unfiltered_live_share_query_failure_does_not_issue_a_grant(real_service):
    service, record, path = real_service
    record = unfiltered_record(service, record)
    service.publish_dashboard(record.id, record.current_revision, {}, "alice")
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE sales")

    with pytest.raises(DashboardPublicationError):
        LiveShareService(service).create(record.id, "alice")
    with service.dao.session(commit=False) as session:
        assert session.query(DashboardLiveShareEntity).count() == 0


def test_unfiltered_live_share_query_failure_keeps_last_good_data(real_service):
    service, record, path = real_service
    record = unfiltered_record(service, record)
    service.publish_dashboard(record.id, record.current_revision, {}, "alice")
    live = LiveShareService(service)
    token = live.create(record.id, "alice")["share_path"].split("/")[-1]
    first = live.read(token)
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE sales")
    expire_cache(service, record.id)
    stale = live.read(token)
    assert stale.stale and stale.refresh_error
    assert "sales" not in stale.refresh_error
    assert stale.snapshot.widgets["total"].rows == [[30.0]]
    assert stale.snapshot.refreshed_at == first.snapshot.refreshed_at
    assert live.read(token).stale

    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sales (region TEXT, amount REAL)")
        connection.execute("INSERT INTO sales VALUES ('North', 50)")
    expire_cache(service, record.id)
    recovered = live.read(token)
    assert not recovered.stale
    assert recovered.snapshot.widgets["total"].rows == [[50.0]]


def test_filtered_live_share_still_requires_bindings_before_query(
    real_service, monkeypatch
):
    service, record, _ = real_service
    schema = record.schema_payload.model_copy(deep=True)
    schema.widgets[0].publication = None
    record = service.update_dashboard(
        record.id, schema, record.current_revision, "alice"
    )
    service.publish_dashboard(
        record.id, record.current_revision, {}, "alice", allow_static_widgets=True
    )
    execute = Mock(wraps=service.query_executor.execute_widget)
    monkeypatch.setattr(service.query_executor, "execute_widget", execute)

    with pytest.raises(DashboardPublicationError, match="Missing bindings: total"):
        LiveShareService(service).create(record.id, "alice")
    execute.assert_not_called()


@pytest.mark.parametrize("action", ["create", "read"])
def test_unfiltered_live_share_checks_source_access_before_query(
    real_service, monkeypatch, action
):
    service, record, _ = real_service
    record = unfiltered_record(service, record)
    service.publish_dashboard(record.id, record.current_revision, {}, "alice")
    live = LiveShareService(service)
    token = None
    if action == "read":
        token = live.create(record.id, "alice")["share_path"].split("/")[-1]
    service.authorization = DashboardAuthorizationService(
        dashboard_dao=service.dao,
        access_dao=Mock(),
        audit_dao=Mock(),
        data_source_authorizer=lambda actor, source: False,
        require_data_source_authorizer=True,
    )
    execute = Mock(wraps=service.query_executor.execute_widget)
    monkeypatch.setattr(service.query_executor, "execute_widget", execute)
    with pytest.raises(DashboardAccessDeniedError):
        if action == "create":
            live.create(record.id, "alice")
        else:
            live.read(token)
    execute.assert_not_called()
