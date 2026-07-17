"""Integration test for the dynamic Alembic migration flow."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Column, Index, Integer, MetaData, String, Table, create_engine
from sqlalchemy import inspect as sqlalchemy_inspect

from dbgpt.storage.metadata import Model
from dbgpt_serve.auth.models.models import (  # noqa: F401
    AccountSetEntity,
    AuditEventEntity,
    ImportBatchEntity,
    SessionEntity,
    TokenDailyEntity,
    TokenUsageEntity,
    UserAccountGrantEntity,
    UserEntity,
    UserResourceGrantEntity,
)

AUTH_TABLES = {
    "dbgpt_auth_user",
    "dbgpt_auth_account_set",
    "dbgpt_auth_user_account_grant",
    "dbgpt_auth_user_resource_grant",
    "dbgpt_auth_import_batch",
    "dbgpt_auth_token_usage",
    "dbgpt_auth_token_daily",
    "dbgpt_auth_audit_event",
    "dbgpt_auth_session",
}

RESOURCE_INDEXES = {
    "connect_config": "idx_connect_account_set",
    "knowledge_space": "idx_ks_account_set",
    "gpts_app": "idx_app_account_set",
}

ALEMBIC_ENV = """from alembic import context

config = context.config
connection = config.attributes["connection"]
target_metadata = config.attributes["target_metadata"]

context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=connection.dialect.name == "sqlite",
    compare_type=True,
)

with context.begin_transaction():
    context.run_migrations()
"""


def _create_baseline(engine) -> None:
    metadata = MetaData()
    for table_name in RESOURCE_INDEXES:
        Table(table_name, metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(engine)


def _build_target_metadata() -> MetaData:
    metadata = MetaData()
    for table_name in AUTH_TABLES:
        Model.metadata.tables[table_name].to_metadata(metadata)
    for table_name, index_name in RESOURCE_INDEXES.items():
        table = Table(
            table_name,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("account_set_id", String(128), nullable=True),
        )
        Index(index_name, table.c.account_set_id)
    return metadata


def _create_alembic_config(tmp_path: Path, target_metadata: MetaData) -> Config:
    script_location = tmp_path / "alembic"
    versions = script_location / "versions"
    versions.mkdir(parents=True)
    (script_location / "env.py").write_text(ALEMBIC_ENV, encoding="utf-8")

    repository_root = Path(__file__).parents[6]
    template = repository_root / "pilot" / "meta_data" / "alembic" / "script.py.mako"
    (script_location / "script.py.mako").write_text(
        template.read_text(encoding="utf-8"), encoding="utf-8"
    )

    ini_path = tmp_path / "alembic.ini"
    ini_path.write_text("[alembic]\n", encoding="utf-8")
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_location))
    config.attributes["target_metadata"] = target_metadata
    return config


def test_alembic_upgrade_and_downgrade_auth_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    _create_baseline(engine)
    config = _create_alembic_config(tmp_path, _build_target_metadata())

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        revision = command.revision(
            config, message="add authorization center tables", autogenerate=True
        )
    assert revision is not None

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    inspector = sqlalchemy_inspect(engine)
    assert AUTH_TABLES <= set(inspector.get_table_names())
    for table_name, index_name in RESOURCE_INDEXES.items():
        assert "account_set_id" in {
            column["name"] for column in inspector.get_columns(table_name)
        }
        assert index_name in {
            index["name"] for index in inspector.get_indexes(table_name)
        }

    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")

    inspector = sqlalchemy_inspect(engine)
    assert AUTH_TABLES.isdisjoint(inspector.get_table_names())
    for table_name in RESOURCE_INDEXES:
        assert "account_set_id" not in {
            column["name"] for column in inspector.get_columns(table_name)
        }
