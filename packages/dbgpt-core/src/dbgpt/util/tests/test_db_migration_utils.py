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
