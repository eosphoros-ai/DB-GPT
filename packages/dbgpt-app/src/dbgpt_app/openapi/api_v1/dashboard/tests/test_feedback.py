import sqlite3
from datetime import datetime, timedelta

import pytest

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.folders import FolderService
from dbgpt_app.openapi.api_v1.dashboard.live_share import (
    DashboardLiveShareEntity,
    LiveShareService,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardDao,
    DashboardNotFoundError,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardCopyRequest,
    DashboardCreateRequest,
    DashboardSchemaV1,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector


@pytest.fixture
def real_service(tmp_path):
    path = tmp_path / "source.db"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE sales (region TEXT, amount REAL)")
        c.executemany("INSERT INTO sales VALUES (?,?)", [("North", 10), ("South", 20)])
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    connector = SQLiteConnector.from_file_path(str(path))
    service = DashboardService(
        dao=DashboardDao(manager), connector_resolver=lambda _: connector
    )
    schema = DashboardSchemaV1.model_validate(
        {
            "schema_version": "1.3",
            "dashboard": {"title": "Live proof", "data_source_id": "test"},
            "filters": [
                {
                    "id": "region",
                    "type": "select",
                    "label": "Region",
                    "field": "region",
                    "default": "all",
                    "options": [
                        {"label": v, "value": v} for v in ["all", "North", "South"]
                    ],
                }
            ],
            "widgets": [
                {
                    "id": "total",
                    "type": "kpi",
                    "title": "Revenue",
                    "encoding": {"value": "value"},
                    "query": {
                        "data_source_id": "test",
                        "sql": (
                            "SELECT SUM(amount) AS value FROM sales WHERE (:r"
                            "egion='all' OR region=:region)"
                        ),
                        "filter_parameters": {"region": {"parameter": "region"}},
                        "output_fields": [{"name": "value", "type": "number"}],
                    },
                    "publication": {
                        "query": {
                            "data_source_id": "test",
                            "sql": "SELECT region,amount FROM sales",
                            "output_fields": [
                                {"name": "region", "type": "string"},
                                {"name": "amount", "type": "number"},
                            ],
                        },
                        "filter_fields": {"region": "region"},
                        "measures": [
                            {
                                "source_field": "amount",
                                "output_field": "value",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["value"],
                    },
                }
            ],
            "layouts": {
                "desktop": [{"widget_id": "total", "x": 0, "y": 0, "w": 12, "h": 4}]
            },
        }
    )
    record = service.create_dashboard(DashboardCreateRequest(schema=schema), "alice")
    return service, record, path


def test_v95_live_link_recovery_preserves_token_and_revision(
    real_service, monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1.dashboard.share_vault import (
        DashboardShareSecretEntity,
    )

    monkeypatch.setenv("DBGPT_SHARE_KEY_FILE", str(tmp_path / "share.key"))
    service, record, _ = real_service
    published = service.publish_dashboard(record.id, 1, {}, "alice")
    live = LiveShareService(service)
    created = live.create(record.id, "alice")
    assert (
        LiveShareService(service).status(record.id, "alice")["share_path"]
        == created["share_path"]
    )
    assert (
        live.status(record.id, "alice")["snapshot_share_path"] == published.share_path
    )
    with service.dao.session() as session:
        for secret in session.query(DashboardShareSecretEntity).all():
            assert created["share_path"].split("/")[-1] not in secret.ciphertext
        session.query(DashboardShareSecretEntity).delete()
    assert live.status(record.id, "alice")["share_path"] is None
    live.read(created["share_path"].split("/")[-1])
    assert live.status(record.id, "alice")["share_path"] == created["share_path"]
    assert service.get_dashboard(record.id, "alice").current_revision == 1
    live.revoke(record.id, "alice")
    assert live.status(record.id, "alice")["share_path"] is None


def test_v95_test_assets_are_separate_before_pagination(real_service):
    service, record, _ = real_service
    copy = service.copy_dashboard(
        record.id, DashboardCopyRequest(title="UAT-验收看板"), "alice"
    )
    main = service.list_dashboard_page("alice", folder_id="__main__", limit=1)
    testing = service.list_dashboard_page("alice", folder_id="__tests__", limit=1)
    assert main.total == 1 and main.items[0].id == record.id
    assert testing.total == 1 and testing.items[0].id == copy.id
    assert service.list_dashboard_page("alice").total == 2


def test_v95_fixed_link_recovery_tracks_rotation_and_valid_legacy_visits(real_service):
    from dbgpt_app.openapi.api_v1.dashboard.share_vault import (
        DashboardShareSecretEntity,
    )

    service, record, _ = real_service
    published = service.publish_dashboard(record.id, 1, {}, "alice")
    rotated = service.rotate_publication(record.id, 1, "alice")
    live = LiveShareService(service)
    assert live.status(record.id, "alice")["snapshot_share_path"] == rotated.share_path
    with pytest.raises(DashboardNotFoundError):
        service.get_public_snapshot(published.share_token)
    with service.dao.session() as session:
        session.query(DashboardShareSecretEntity).delete()
    assert live.status(record.id, "alice")["snapshot_share_path"] is None
    service.get_public_snapshot(rotated.share_token)
    assert live.status(record.id, "alice")["snapshot_share_path"] == rotated.share_path
    service.revoke_publication(record.id, 1, "alice")
    assert live.status(record.id, "alice")["snapshot_share_path"] is None
    assert service.get_dashboard(record.id, "alice").current_revision == 1


def test_v95_scheduler_status_uses_actual_runner_state():
    from unittest.mock import Mock

    from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService

    scheduler = Mock()
    scheduler.is_running.return_value = False
    service = ScheduledTaskService(scheduler=scheduler)
    assert service.execution_status()["running"] is False
    scheduler.is_running.return_value = True
    assert service.execution_status()["running"] is True


def test_same_live_link_reads_new_source_rows_without_republish(real_service):
    service, record, path = real_service
    published = service.publish_dashboard(record.id, 1, {}, "alice")
    frozen = published.share_token
    live = LiveShareService(service)
    token = live.create(record.id, "alice")["share_path"].split("/")[-1]
    first = live.read(token)
    assert first.snapshot.widgets["total"].rows == [[30.0]]
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO sales VALUES ('North',7)")
    assert live.read(token).snapshot.widgets["total"].rows == [[30.0]]  # bounded cache
    with service.dao.session() as s:
        s.query(DashboardLiveShareEntity).filter_by(dashboard_id=record.id).update(
            {"last_attempt_at": datetime.now() - timedelta(seconds=61)}
        )
    fresh = live.read(token)
    assert fresh.snapshot.widgets["total"].rows == [[37.0]]
    assert live.read(token, {"region": "North"}).snapshot.widgets["total"].rows == [
        [17.0]
    ]
    assert fresh.published_revision == published.published_revision
    assert service.get_dashboard(record.id, "alice").current_revision == 1
    assert len(service.list_revisions(record.id, "alice")) == 1
    assert service.get_public_snapshot(frozen).snapshot.widgets["total"].rows == [
        [30.0]
    ]
    live.revoke(record.id, "alice")
    with pytest.raises(DashboardNotFoundError):
        live.read(token)


def test_personal_folders_scope_before_pagination_and_preserve_revision(real_service):
    service, record, _ = real_service
    folders = FolderService(service)
    apple = folders.save("alice", "Apple")
    assert folders.list("bob") == []
    with pytest.raises(DashboardNotFoundError):
        folders.move("alice", record.id, "foreign-folder")
    folders.move("alice", record.id, apple["id"])
    assert (
        service.list_dashboard_page("alice", folder_id=apple["id"], limit=1).total == 1
    )
    assert service.list_dashboard_page("alice", folder_id="unfiled").total == 0
    folders.save("alice", "财务", apple["id"])
    folders.delete("alice", apple["id"])
    assert service.list_dashboard_page("alice", folder_id="unfiled").total == 1
    assert service.get_dashboard(record.id, "alice").current_revision == 1


def test_copied_manual_dashboard_gets_one_stable_continuation(real_service):
    service, record, _ = real_service
    assert record.conversation_id is None
    one = service.dao.ensure_assistant_conversation(record.id, "alice")
    two = service.dao.ensure_assistant_conversation(record.id, "alice")
    assert one == two
    after = service.get_dashboard(record.id, "alice")
    assert after.conversation_id == after.schema_payload.metadata.conversation_id == one
    assert after.current_revision == 1


def test_live_failure_retains_timestamp_and_cached_data_then_recovers(
    real_service, monkeypatch
):
    service, record, _ = real_service
    service.publish_dashboard(record.id, 1, {}, "alice")
    live = LiveShareService(service)
    token = live.create(record.id, "alice")["share_path"].split("/")[-1]
    first = live.read(token)
    materialize = live._materialize
    with service.dao.session() as s:
        s.query(DashboardLiveShareEntity).update(
            {"last_attempt_at": datetime.now() - timedelta(seconds=61)}
        )

    def offline(*_):
        raise RuntimeError("private source connection detail must never escape")

    monkeypatch.setattr(live, "_materialize", offline)
    stale = live.read(token)
    assert stale.stale and stale.refresh_error
    assert "private source" not in stale.refresh_error
    assert stale.snapshot.refreshed_at == first.snapshot.refreshed_at
    assert stale.snapshot.widgets["total"].rows == [[30.0]]
    assert live.read(token).stale  # cached failure remains visibly stale
    monkeypatch.setattr(live, "_materialize", materialize)
    with service.dao.session() as s:
        s.query(DashboardLiveShareEntity).update(
            {"last_attempt_at": datetime.now() - timedelta(seconds=61)}
        )
    assert not live.read(token).stale


def test_live_rotation_and_expiry_invalidate_prior_tokens(real_service):
    service, record, _ = real_service
    service.publish_dashboard(record.id, 1, {}, "alice")
    live = LiveShareService(service)
    old = live.create(record.id, "alice")["share_path"].split("/")[-1]
    new = live.create(record.id, "alice")["share_path"].split("/")[-1]
    with pytest.raises(DashboardNotFoundError):
        live.read(old)
    assert live.read(new).snapshot.widgets["total"].rows == [[30.0]]
    with service.dao.session() as s:
        s.query(DashboardLiveShareEntity).update(
            {"expires_at": datetime.now() - timedelta(seconds=1)}
        )
    assert not live.status(record.id, "alice")["active"]
    with pytest.raises(DashboardNotFoundError):
        live.read(new)


def test_dashboard_source_history_keeps_upstream_pagination_and_user_scope(
    real_service, monkeypatch
):
    from dbgpt_serve.conversation.api.schemas import ServeRequest
    from dbgpt_serve.conversation.config import ServeConfig
    from dbgpt_serve.conversation.models.models import ServeDao, ServeEntity

    service, _, _ = real_service
    dao = ServeDao(ServeConfig())
    monkeypatch.setattr(dao, "session", service.dao.session)
    with dao.session() as session:
        ServeEntity.metadata.create_all(session.get_bind())
        for user, count in [("alice", 130), ("bob", 3)]:
            session.add_all(
                [
                    ServeEntity(
                        conv_uid=f"{user}-{i}",
                        chat_mode="chat_react_agent",
                        summary=f"Business question {i}",
                        user_name=user,
                        gmt_created=datetime(2026, 9, 1) + timedelta(minutes=i),
                    )
                    for i in range(count)
                ]
            )
    req = ServeRequest(user_name="alice", chat_mode="chat_react_agent")
    first = dao.get_conv_by_page(req, 1, 20)
    fifth = dao.get_conv_by_page(req, 5, 20)
    # The optional site-wide 100-conversation window is outside this candidate.
    # Dashboard source conversations remain available through upstream paging.
    assert first.total_count == 130 and first.total_pages == 7
    assert first.items[0].conv_uid == "alice-129"
    assert fifth.items[-1].conv_uid == "alice-30"
    assert dao.get_conv_by_page(req, 7, 20).items[-1].conv_uid == "alice-0"
    assert len(dao.get_conv_by_page(req, 1, 1000).items) == 130
    assert dao.get_conv_by_page(ServeRequest(user_name="bob"), 1, 20).total_count == 3
    with dao.session(commit=False) as session:
        assert session.query(ServeEntity).count() == 133
