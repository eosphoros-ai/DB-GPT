from datetime import datetime

import pytest
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardConflictError,
    DashboardDao,
    DashboardEditVersionEntity,
    DashboardEntity,
    DashboardRevisionEntity,
    DashboardShareEntity,
)


@pytest.fixture
def dao():
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    return DashboardDao(manager)


def entity():
    now = datetime.now()
    return DashboardEntity(
        id="dashboard-1",
        owner_id="alice",
        conversation_id="conv-1",
        title="Sales",
        description="Fixture",
        data_source_id="walmart",
        schema_json='{"schema_version":"1.0"}',
        current_revision=1,
        status="draft",
        gmt_created=now,
        gmt_modified=now,
    )


def test_sqlite_crud_and_owner_isolation(dao):
    created = dao.create_dashboard(entity())
    assert created.id == "dashboard-1"
    assert dao.get_dashboard("dashboard-1", "bob") is None
    assert [row.id for row in dao.list_dashboards("alice")] == ["dashboard-1"]
    assert [row.revision for row in dao.list_edit_versions("dashboard-1")] == [1]

    updated = dao.update_dashboard(
        "dashboard-1",
        "alice",
        1,
        title="Updated sales",
        description="Updated",
        data_source_id="walmart",
        schema_json='{"schema_version":"1.0","updated":true}',
    )
    assert updated.current_revision == 2
    assert updated.status == "draft"
    versions = dao.list_edit_versions("dashboard-1")
    assert [row.revision for row in versions] == [2, 1]
    assert versions[0].schema_json == '{"schema_version":"1.0","updated":true}'
    assert dao.get_edit_version("dashboard-1", 1).schema_json == (
        '{"schema_version":"1.0"}'
    )
    with pytest.raises(DashboardConflictError):
        dao.update_dashboard(
            "dashboard-1",
            "alice",
            1,
            title="Stale edit",
            description="",
            data_source_id="walmart",
            schema_json="{}",
        )


def test_published_revisions_are_immutable_rows(dao):
    dao.create_dashboard(entity())
    first, _ = dao.publish_dashboard(
        "dashboard-1",
        "alice",
        1,
        schema_json='{"title":"v1"}',
        snapshot_json='{"widgets":{}}',
        validation_json='{"valid":true}',
        share_token_hash="a" * 64,
    )
    second, _ = dao.publish_dashboard(
        "dashboard-1",
        "alice",
        1,
        schema_json='{"title":"v1 republished"}',
        snapshot_json='{"widgets":{}}',
        validation_json='{"valid":true}',
        share_token_hash="b" * 64,
    )
    assert (first.revision, second.revision) == (1, 2)
    assert dao.get_published_by_token_hash("a" * 64).schema_json == '{"title":"v1"}'
    assert (
        dao.get_published_by_token_hash("b" * 64).schema_json
        == '{"title":"v1 republished"}'
    )


def test_share_rotation_and_revocation_leave_published_revision_immutable(dao):
    dao.create_dashboard(entity())
    first, _ = dao.publish_dashboard(
        "dashboard-1",
        "alice",
        1,
        schema_json='{"title":"v1"}',
        snapshot_json='{"widgets":{}}',
        validation_json='{"valid":true}',
        share_token_hash="a" * 64,
        share_created_by="alice",
    )

    rotated = dao.rotate_share(
        "dashboard-1",
        first.revision,
        "b" * 64,
        created_by="alice",
    )

    assert dao.get_active_published_by_token_hash("a" * 64) is None
    assert dao.get_active_published_by_token_hash("b" * 64).schema_json == (
        '{"title":"v1"}'
    )
    assert rotated.revision == first.revision
    assert dao.revoke_shares("dashboard-1", first.revision) == 1
    assert dao.get_active_published_by_token_hash("b" * 64) is None
    assert dao.get_published_by_token_hash("a" * 64).schema_json == '{"title":"v1"}'


def test_history_retains_twenty_combined_versions_without_renumbering(dao):
    dao.create_dashboard(entity())
    token_hashes = []

    for number in range(1, 23):
        token_hash = f"{number:064x}"
        token_hashes.append(token_hash)
        published, _ = dao.publish_dashboard(
            "dashboard-1",
            "alice",
            1,
            schema_json=f'{{"title":"v{number}"}}',
            snapshot_json='{"widgets":{}}',
            validation_json='{"valid":true}',
            share_token_hash=token_hash,
            share_created_by="alice",
        )
        assert published.revision == number

    revisions = dao.list_published_revisions("dashboard-1")
    assert [row.revision for row in revisions] == list(range(22, 3, -1))
    assert len(revisions) + len(dao.list_edit_versions("dashboard-1")) == 20
    assert len(dao.list_shares("dashboard-1")) == 19
    assert dao.get_published_by_token_hash(token_hashes[0]) is None
    assert dao.get_active_published_by_token_hash(token_hashes[0]) is None
    assert dao.get_active_published_by_token_hash(token_hashes[-1]).revision == 22
    assert dao.get_latest_published_revision("dashboard-1").revision == 22


def test_public_slug_is_stable_across_publications(dao):
    dao.create_dashboard(entity())
    _, first_dashboard = dao.publish_dashboard(
        "dashboard-1",
        "alice",
        1,
        schema_json='{"title":"v1"}',
        snapshot_json='{"widgets":{}}',
        validation_json='{"valid":true}',
        share_token_hash="a" * 64,
        public_slug="stable-public-id",
    )
    _, second_dashboard = dao.publish_dashboard(
        "dashboard-1",
        "alice",
        1,
        schema_json='{"title":"v2"}',
        snapshot_json='{"widgets":{}}',
        validation_json='{"valid":true}',
        share_token_hash="b" * 64,
        public_slug="ignored-replacement",
    )

    assert first_dashboard.public_slug == "stable-public-id"
    assert second_dashboard.public_slug == "stable-public-id"
    assert dao.get_dashboard_by_public_slug("stable-public-id").id == "dashboard-1"


def test_tables_have_database_agnostic_sqlalchemy_types():
    dashboard_columns = {column.name for column in DashboardEntity.__table__.columns}
    revision_columns = {
        column.name for column in DashboardRevisionEntity.__table__.columns
    }
    assert {
        "schema_json",
        "current_revision",
        "owner_id",
        "public_slug",
    } <= dashboard_columns
    assert {"snapshot_json", "share_token_hash", "revision"} <= revision_columns
    assert {"schema_json", "source", "actor_id", "operation_id"} <= {
        column.name for column in DashboardEditVersionEntity.__table__.columns
    }
    assert {"dashboard_id", "revision", "token_hash", "expires_at"} <= {
        column.name for column in DashboardShareEntity.__table__.columns
    }


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect()])
def test_table_ddl_compiles_for_sqlite_and_mysql(dialect):
    for table in (
        DashboardEntity.__table__,
        DashboardEditVersionEntity.__table__,
        DashboardRevisionEntity.__table__,
        DashboardShareEntity.__table__,
    ):
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in ddl


def test_snapshot_columns_use_mysql_longtext_without_changing_sqlite():
    mysql_ddl = str(
        CreateTable(DashboardRevisionEntity.__table__).compile(dialect=mysql.dialect())
    ).upper()
    sqlite_ddl = str(
        CreateTable(DashboardRevisionEntity.__table__).compile(dialect=sqlite.dialect())
    ).upper()

    assert "SNAPSHOT_JSON LONGTEXT" in mysql_ddl
    assert "SNAPSHOT_JSON TEXT" in sqlite_ddl
    assert (
        "SCHEMA_JSON LONGTEXT"
        in str(
            CreateTable(DashboardEditVersionEntity.__table__).compile(
                dialect=mysql.dialect()
            )
        ).upper()
    )
