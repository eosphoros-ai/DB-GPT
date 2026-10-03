import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_revision(filename: str):
    root = Path(__file__).parents[8]
    path = root / "pilot" / "meta_data" / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(module, connection, function_name: str):
    module.op = Operations(MigrationContext.configure(connection))
    getattr(module, function_name)()


@pytest.mark.parametrize("precreated", [False, True])
def test_share_secret_migration_preserves_ciphertext_and_supports_downgrade(
    tmp_path, precreated
):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'share-secrets.db'}")
    revision = _load_revision("20260929_0015_dashboard_share_secrets.py")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE unrelated_data (value INTEGER)"))
        connection.execute(sa.text("INSERT INTO unrelated_data VALUES (7)"))
        if precreated:
            connection.execute(
                sa.text(
                    "CREATE TABLE dbgpt_dashboard_share_secret "
                    "(token_hash VARCHAR(64) PRIMARY KEY, "
                    "ciphertext VARCHAR(512) NOT NULL)"
                )
            )
        _run(revision, connection, "upgrade")
        connection.execute(
            sa.text(
                "INSERT INTO dbgpt_dashboard_share_secret VALUES (:digest, :ciphertext)"
            ),
            {"digest": "a" * 64, "ciphertext": "existing-encrypted-copy"},
        )
        _run(revision, connection, "upgrade")
        assert (
            connection.execute(
                sa.text("SELECT ciphertext FROM dbgpt_dashboard_share_secret")
            ).scalar_one()
            == "existing-encrypted-copy"
        )
        _run(revision, connection, "downgrade")
        _run(revision, connection, "downgrade")
        assert not sa.inspect(connection).has_table("dbgpt_dashboard_share_secret")
        assert (
            connection.execute(sa.text("SELECT value FROM unrelated_data")).scalar_one()
            == 7
        )
        _run(revision, connection, "upgrade")
        assert (
            connection.execute(
                sa.text("SELECT COUNT(*) FROM dbgpt_dashboard_share_secret")
            ).scalar_one()
            == 0
        )


def test_trace_link_upgrade_preserves_existing_messages_and_is_repeatable(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old-chat.db'}")
    revision = _load_revision("20260926_0014_upstream_trace_link.py")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                (
                    "CREATE TABLE chat_history_message (id INTEGER PR"
                    "IMARY KEY, message_detail TEXT)"
                )
            )
        )
        connection.execute(
            sa.text("INSERT INTO chat_history_message VALUES (1, 'original message')")
        )
        _run(revision, connection, "upgrade")
        _run(revision, connection, "upgrade")
        assert connection.execute(
            sa.text("SELECT message_detail, trace_id FROM chat_history_message")
        ).one() == ("original message", None)
        assert "ix_chat_history_message_trace_id" in {
            item["name"]
            for item in sa.inspect(connection).get_indexes("chat_history_message")
        }


def test_dashboard_migrations_upgrade_existing_v1_and_backfill_owner(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    baseline = _load_revision("20260811_0001_dashboard_v1_baseline.py")
    rbac = _load_revision("20260811_0002_dashboard_rbac_audit.py")
    schedules = _load_revision("20260811_0003_dashboard_schedules.py")
    collaboration = _load_revision("20260811_0004_dashboard_collaboration.py")
    shares = _load_revision("20260812_0005_dashboard_shares.py")
    task_assets = _load_revision("20260814_0006_dashboard_task_assets.py")
    annotations = _load_revision("20260816_0007_dashboard_annotations.py")
    deployed_compat = _load_revision("20260830_0000_dashboard_v38_compat.py")
    latest_share = _load_revision("20260830_0008_dashboard_latest_public_link.py")
    annotation_intent = _load_revision("20260831_0009_dashboard_annotation_intent.py")
    upload_registry = _load_revision("20260831_0010_uploaded_dataset_registry.py")
    edit_versions = _load_revision("20260831_0011_dashboard_edit_versions.py")

    with engine.begin() as connection:
        _run(baseline, connection, "upgrade")
        connection.execute(
            sa.text(
                """
                INSERT INTO dbgpt_dashboard
                    (id, owner_id, title, data_source_id, schema_json,
                     current_revision, status, gmt_created, gmt_modified)
                VALUES
                    ('dashboard-1', 'alice', 'Sales', 'sales', '{}',
                     1, 'draft', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                    ('walmart-sales-demo', 'alice', 'Walmart demo', 'sales', '{}',
                     1, 'draft', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            )
        )
        # The baseline and RBAC revisions are safe for an early-preview database.
        _run(baseline, connection, "upgrade")
        _run(rbac, connection, "upgrade")
        _run(rbac, connection, "upgrade")
        _run(schedules, connection, "upgrade")
        _run(schedules, connection, "upgrade")
        _run(collaboration, connection, "upgrade")
        _run(collaboration, connection, "upgrade")
        connection.execute(
            sa.text(
                """
                INSERT INTO dbgpt_dashboard_revision
                    (dashboard_id, revision, schema_json, snapshot_json,
                     validation_json, share_token_hash, gmt_published)
                VALUES
                    ('dashboard-1', 1, '{}', '{}', '{}', :token,
                     CURRENT_TIMESTAMP)
                """
            ),
            {"token": "a" * 64},
        )
        _run(shares, connection, "upgrade")
        _run(shares, connection, "upgrade")
        _run(task_assets, connection, "upgrade")
        _run(task_assets, connection, "upgrade")
        _run(annotations, connection, "upgrade")
        _run(annotations, connection, "upgrade")
        _run(deployed_compat, connection, "upgrade")
        _run(deployed_compat, connection, "upgrade")
        _run(latest_share, connection, "upgrade")
        _run(latest_share, connection, "upgrade")
        _run(annotation_intent, connection, "upgrade")
        _run(annotation_intent, connection, "upgrade")
        _run(upload_registry, connection, "upgrade")
        _run(upload_registry, connection, "upgrade")
        _run(edit_versions, connection, "upgrade")
        _run(edit_versions, connection, "upgrade")

        member = connection.execute(
            sa.text(
                "SELECT principal_id, role FROM dbgpt_dashboard_member "
                "WHERE dashboard_id = 'dashboard-1'"
            )
        ).one()
        assert tuple(member) == ("alice", "owner")
        assert set(sa.inspect(connection).get_table_names()) >= {
            "dbgpt_dashboard",
            "dbgpt_dashboard_revision",
            "dbgpt_dashboard_member",
            "dbgpt_dashboard_audit",
            "dbgpt_serve_scheduled_task",
            "dbgpt_serve_scheduled_run",
            "dbgpt_dashboard_operation",
            "dbgpt_dashboard_share",
            "dbgpt_dashboard_annotation",
            "dbgpt_uploaded_dataset",
            "dbgpt_dashboard_edit_version",
        }

        edit_version = connection.execute(
            sa.text(
                "SELECT dashboard_id, revision, source, actor_id "
                "FROM dbgpt_dashboard_edit_version "
                "WHERE dashboard_id = 'dashboard-1'"
            )
        ).one()
        assert tuple(edit_version) == ("dashboard-1", 1, "migration", "alice")

        share = connection.execute(
            sa.text(
                "SELECT dashboard_id, revision, token_hash, created_by "
                "FROM dbgpt_dashboard_share"
            )
        ).one()
        assert tuple(share) == ("dashboard-1", 1, "a" * 64, "alice")

        lifecycle = connection.execute(
            sa.text(
                "SELECT origin, asset_state, saved_at FROM dbgpt_dashboard "
                "WHERE id = 'dashboard-1'"
            )
        ).one()
        assert lifecycle.origin == "manual"
        assert lifecycle.asset_state == "saved"
        assert lifecycle.saved_at is not None
        template_origin = connection.execute(
            sa.text(
                "SELECT origin FROM dbgpt_dashboard WHERE id = 'walmart-sales-demo'"
            )
        ).scalar_one()
        assert template_origin == "template"
        dashboard_columns = {
            column["name"]
            for column in sa.inspect(connection).get_columns("dbgpt_dashboard")
        }
        assert "public_slug" in dashboard_columns
        annotation_columns = {
            column["name"]
            for column in sa.inspect(connection).get_columns(
                "dbgpt_dashboard_annotation"
            )
        }
        assert "intent" in annotation_columns

        task_columns = {
            column["name"]
            for column in sa.inspect(connection).get_columns(
                "dbgpt_serve_scheduled_task"
            )
        }
        assert {
            "owner_id",
            "resource_type",
            "resource_id",
            "lease_owner",
            "lease_expires_at",
        } <= task_columns

        _run(rbac, connection, "downgrade")
        remaining = set(sa.inspect(connection).get_table_names())
        assert "dbgpt_dashboard" in remaining
        assert "dbgpt_dashboard_member" not in remaining


def test_alembic_upgrade_uses_supplied_connection_and_committed_revisions(tmp_path):
    root = Path(__file__).parents[8]
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'alembic.db'}")
    config = Config(str(root / "pilot" / "meta_data" / "alembic.ini"))
    config.set_main_option(
        "script_location", str(root / "pilot" / "meta_data" / "alembic")
    )
    config.attributes["target_metadata"] = sa.MetaData()

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    tables = set(sa.inspect(engine).get_table_names())
    assert {
        "alembic_version",
        "dbgpt_dashboard",
        "dbgpt_dashboard_revision",
        "dbgpt_dashboard_member",
        "dbgpt_dashboard_audit",
        "dbgpt_serve_scheduled_task",
        "dbgpt_serve_scheduled_run",
        "dbgpt_dashboard_operation",
        "dbgpt_dashboard_share",
        "dbgpt_dashboard_annotation",
        "dbgpt_uploaded_dataset",
        "dbgpt_dashboard_edit_version",
        "dbgpt_dashboard_share_secret",
    } <= tables
    dashboard_columns = {
        column["name"] for column in sa.inspect(engine).get_columns("dbgpt_dashboard")
    }
    assert {
        "source_turn_id",
        "origin",
        "asset_state",
        "saved_at",
        "public_slug",
    } <= dashboard_columns
    with engine.connect() as connection:
        assert (
            connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "20260929_dashboard_share_secrets"
        )


@pytest.mark.parametrize(
    "legacy_revision", ["f8bd7ecc3d5f", "cd2ea32f532b", "2757edbd890f"]
)
def test_alembic_upgrades_database_stamped_with_local_revision(
    tmp_path, legacy_revision
):
    root = Path(__file__).parents[8]
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'v38-upgrade.db'}")
    pre_v38 = [
        _load_revision("20260811_0001_dashboard_v1_baseline.py"),
        _load_revision("20260811_0002_dashboard_rbac_audit.py"),
        _load_revision("20260811_0003_dashboard_schedules.py"),
        _load_revision("20260811_0004_dashboard_collaboration.py"),
        _load_revision("20260812_0005_dashboard_shares.py"),
        _load_revision("20260814_0006_dashboard_task_assets.py"),
        _load_revision("20260816_0007_dashboard_annotations.py"),
    ]
    config = Config(str(root / "pilot" / "meta_data" / "alembic.ini"))
    config.set_main_option(
        "script_location", str(root / "pilot" / "meta_data" / "alembic")
    )
    config.attributes["target_metadata"] = sa.MetaData()

    with engine.begin() as connection:
        for revision_module in pre_v38:
            _run(revision_module, connection, "upgrade")
        config.attributes["connection"] = connection
        command.stamp(config, legacy_revision)
        command.upgrade(config, "head")

    inspector = sa.inspect(engine)
    assert "dbgpt_dashboard_edit_version" in inspector.get_table_names()
    assert "intent" in {
        column["name"] for column in inspector.get_columns("dbgpt_dashboard_annotation")
    }
    with engine.connect() as connection:
        assert (
            connection.execute(
                sa.text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "20260929_dashboard_share_secrets"
        )


def test_edit_version_migration_backfills_a_precreated_empty_table(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'precreated-version.db'}")
    metadata = sa.MetaData()
    dashboard = sa.Table(
        "dbgpt_dashboard",
        metadata,
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("schema_json", sa.Text(), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("gmt_modified", sa.DateTime(), nullable=False),
    )
    sa.Table(
        "dbgpt_dashboard_edit_version",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dashboard_id", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=True),
        sa.Column("gmt_created", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dashboard_id", "revision"),
    )
    metadata.create_all(engine)
    migration = _load_revision("20260831_0011_dashboard_edit_versions.py")

    with engine.begin() as connection:
        connection.execute(
            dashboard.insert().values(
                id="dashboard-precreated",
                owner_id="alice",
                schema_json='{"schema_version":"1.0"}',
                current_revision=7,
                gmt_modified=datetime(2026, 8, 31),
            )
        )
        _run(migration, connection, "upgrade")
        _run(migration, connection, "upgrade")
        rows = connection.execute(
            sa.text(
                "SELECT dashboard_id, revision, source, actor_id "
                "FROM dbgpt_dashboard_edit_version"
            )
        ).all()

    assert [tuple(row) for row in rows] == [
        ("dashboard-precreated", 7, "migration", "alice")
    ]
