"""Tests for _db_migration_utils create_alembic_config behaviour."""

from unittest.mock import MagicMock, patch


def test_create_alembic_config_creates_versions_dir(tmp_path):
    """create_alembic_config must create script_location and versions/ directories."""
    from dbgpt.util._db_migration_utils import create_alembic_config

    mock_engine = MagicMock()
    mock_engine.url = "sqlite:///test.db"
    mock_base = MagicMock()
    mock_base.metadata = MagicMock()
    mock_session = MagicMock()

    alembic_root = str(tmp_path)

    with patch("dbgpt.util._db_migration_utils.AlembicConfig") as mock_alembic_cfg_cls:
        mock_cfg = MagicMock()
        mock_alembic_cfg_cls.return_value = mock_cfg

        result = create_alembic_config(
            alembic_root, mock_engine, mock_base, mock_session
        )

    alembic_dir = tmp_path / "alembic"
    versions_dir = alembic_dir / "versions"
    assert alembic_dir.exists(), "script_location directory must be created"
    assert versions_dir.exists(), "versions directory must be created"
    assert result is mock_cfg


def test_runtime_upgrade_does_not_create_empty_revision():
    """Opening a current database must never manufacture a migration file."""
    from dbgpt.util._db_migration_utils import _ddl_init_and_upgrade

    mock_db = MagicMock()
    mock_db.engine = MagicMock()
    mock_db.Model = MagicMock()
    mock_db.session.return_value = MagicMock()
    mock_cfg = MagicMock()

    with (
        patch("dbgpt.storage.metadata.db_manager.db", mock_db),
        patch(
            "dbgpt.util._db_migration_utils.create_alembic_config",
            return_value=mock_cfg,
        ),
        patch("dbgpt.util._db_migration_utils._check_database_migration_status"),
        patch(
            "dbgpt.util._db_migration_utils._get_latest_revision",
            return_value="head",
        ),
        patch(
            "dbgpt.util._db_migration_utils.create_migration_script"
        ) as create_script,
        patch("dbgpt.util._db_migration_utils.upgrade_database") as upgrade,
    ):
        _ddl_init_and_upgrade("metadata", disable_alembic_upgrade=False)

    create_script.assert_called_once_with(
        mock_cfg,
        mock_db.engine,
        create_new_revision_if_noting_to_update=False,
    )
    upgrade.assert_called_once_with(mock_cfg, mock_db.engine)
