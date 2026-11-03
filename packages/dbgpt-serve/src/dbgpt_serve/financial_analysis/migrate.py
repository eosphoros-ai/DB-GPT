"""Explicit, additive migration. Never reads the application's configured DB.

Run with --database-url pointing to the intended, backed-up database.
Supports SQLite, PostgreSQL and MySQL. Do not run an old application over new
comparison tasks; downgrade requires exporting and removing those tasks first.
"""

import argparse
import json

from sqlalchemy import create_engine, inspect, text

from .models import (
    FinancialExportEntity,
    FinancialReportRevisionEntity,
    FinancialRunDocumentEntity,
    FinancialRunEntity,
)

TABLE = FinancialRunEntity.__tablename__
ADDITIONS = {
    "mode": "VARCHAR(16) NOT NULL DEFAULT 'report'",
    "config_json": "TEXT",
    "request_fingerprint": "VARCHAR(64)",
}


def migration_plan(engine):
    dialect = engine.dialect.name
    if dialect not in {"sqlite", "mysql", "postgresql"}:
        raise ValueError("Supported migration dialects: sqlite, mysql, postgresql")
    inspector = inspect(engine)
    if not inspector.has_table(TABLE):
        return []
    names = {c["name"] for c in inspector.get_columns(TABLE)}
    return [
        f"ALTER TABLE {TABLE} ADD COLUMN {name} "
        + ("LONGTEXT" if name == "config_json" and dialect == "mysql" else ddl)
        for name, ddl in ADDITIONS.items()
        if name not in names
    ]


def migrate(engine, *, apply=False):
    statements = migration_plan(engine)
    if not apply:
        return statements
    # MySQL DDL commits implicitly. Every step is additive and repeatable; never
    # remove old columns or claim that multi-statement DDL rolls back atomically.
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    for model in (
        FinancialRunEntity,
        FinancialExportEntity,
        FinancialRunDocumentEntity,
        FinancialReportRevisionEntity,
    ):
        model.__table__.create(engine, checkfirst=True)
    return statements


def ensure_schema(engine, *, allow_legacy=False):
    statements = migration_plan(engine)
    if statements:
        # An untouched v1 database can still serve single reports. A partially
        # migrated schema must be finished explicitly, never guessed at.
        if allow_legacy and len(statements) == len(ADDITIONS):
            return False
        raise RuntimeError(
            "Financial comparison schema migration required. Run the explicit "
            "dbgpt_serve.financial_analysis.migrate command against the intended DB."
        )
    for model in (
        FinancialRunEntity,
        FinancialExportEntity,
        FinancialRunDocumentEntity,
        FinancialReportRevisionEntity,
    ):
        model.__table__.create(engine, checkfirst=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    engine = create_engine(args.database_url)
    try:
        print(
            json.dumps(
                {"statements": migrate(engine, apply=args.apply), "applied": args.apply}
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
