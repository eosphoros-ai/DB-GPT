import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from dbgpt.app.base import _create_mysql_database


@patch("sqlalchemy.create_engine")
@patch("dbgpt.app.base.logger")
def test_database_already_exists(mock_logger, mock_create_engine):
    mock_connection = MagicMock()
    mock_create_engine.return_value.connect.return_value.__enter__.return_value = (
        mock_connection
    )

    _create_mysql_database(
        "test_db", "mysql+pymysql://user:password@host/test_db", True
    )
    mock_logger.info.assert_called_with("Database test_db already exists")
    mock_connection.execute.assert_not_called()


@patch("sqlalchemy.create_engine")
@patch("dbgpt.app.base.logger")
def test_database_creation_success(mock_logger, mock_create_engine):
    # Mock the first connection failure, and the second connection success
    mock_create_engine.side_effect = [
        MagicMock(
            connect=MagicMock(
                side_effect=OperationalError("Unknown database", None, None)
            )
        ),
        MagicMock(),
    ]

    _create_mysql_database(
        "test_db", "mysql+pymysql://user:password@host/test_db", True
    )
    mock_logger.info.assert_called_with("Database test_db successfully created")


@patch("sqlalchemy.create_engine")
@patch("dbgpt.app.base.logger")
def test_database_creation_failure(mock_logger, mock_create_engine):
    # Mock the first connection failure, and the second connection failure with SQLAlchemyError
    mock_create_engine.side_effect = [
        MagicMock(
            connect=MagicMock(
                side_effect=OperationalError("Unknown database", None, None)
            )
        ),
        MagicMock(connect=MagicMock(side_effect=SQLAlchemyError("Creation failed"))),
    ]

    with pytest.raises(SQLAlchemyError):
        _create_mysql_database(
            "test_db", "mysql+pymysql://user:password@host/test_db", True
        )
    mock_logger.error.assert_called_with(
        "Failed to create database test_db: Creation failed"
    )


@patch("sqlalchemy.create_engine")
@patch("dbgpt.app.base.logger")
def test_skip_database_creation(mock_logger, mock_create_engine):
    _create_mysql_database(
        "test_db", "mysql+pymysql://user:password@host/test_db", False
    )
    mock_logger.info.assert_called_with("Skipping creation of database test_db")
    mock_create_engine.assert_not_called()
