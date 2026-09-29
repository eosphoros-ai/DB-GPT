"""Reproducibly download, load, and verify the Olist demo data source.

The default SQLite destination is anchored to this checkout, so a v3.8 server
never silently registers a database from an older branch or worktree.  A MySQL
URL may be supplied to load and verify the same source rows in both engines.
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .download_olist import resolve_source_files
    from .load_olist import _engine, load_dataset
    from .verify_dashboard_schema import verify as verify_dashboard
    from .verify_olist import verify as verify_answers
except ImportError:  # Support direct script execution from the repository root.
    from download_olist import resolve_source_files
    from load_olist import _engine, load_dataset
    from verify_dashboard_schema import verify as verify_dashboard
    from verify_olist import verify as verify_answers

ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE = ROOT / "data" / "generated" / "olist.db"


def _load(url: str, source_dir: Path, *, include_geolocation: bool) -> None:
    engine = _engine(url)
    try:
        load_dataset(
            engine,
            source_dir,
            include_geolocation=include_geolocation,
            replace=True,
        )
    finally:
        engine.dispose()


def initialize(
    *,
    sqlite_path: Path = DEFAULT_SQLITE,
    mysql_url: str | None = None,
    include_geolocation: bool = False,
    force_download: bool = False,
    verify: bool = True,
) -> None:
    source_dir = resolve_source_files(
        ROOT / "data" / "raw", force=force_download
    ).resolve()
    if (
        include_geolocation
        and not (source_dir / "olist_geolocation_dataset.csv").is_file()
    ):
        raise FileNotFoundError(
            "The optional geolocation table requires the pinned Kaggle archive; "
            "the verified fallback mirror intentionally contains only the eight "
            "required demo tables."
        )
    sqlite_path = sqlite_path.resolve()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_url = f"sqlite:///{sqlite_path.as_posix()}"
    _load(sqlite_url, source_dir, include_geolocation=include_geolocation)
    if verify:
        verify_answers(sqlite_url)

        from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

        connector = SQLiteConnector.from_file_path(str(sqlite_path))
        try:
            verify_dashboard(connector)
        finally:
            connector.close()

    if mysql_url:
        _load(mysql_url, source_dir, include_geolocation=include_geolocation)
        if verify:
            verify_answers(mysql_url)

            from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector

            connector = MySQLConnector.from_uri(mysql_url)
            try:
                verify_dashboard(connector)
            finally:
                connector.close()

    print(f"Olist demo SQLite database ready at {sqlite_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument(
        "--mysql-url",
        help="Optional SQLAlchemy/MySQL connector URL loaded from the same CSVs.",
    )
    parser.add_argument("--include-geolocation", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()
    initialize(
        sqlite_path=args.sqlite,
        mysql_url=args.mysql_url,
        include_geolocation=args.include_geolocation,
        force_download=args.force_download,
        verify=not args.skip_verify,
    )


if __name__ == "__main__":
    main()
