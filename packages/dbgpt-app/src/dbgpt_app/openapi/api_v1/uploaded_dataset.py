"""Turn a bounded tabular upload group into one reusable SQLite data source."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

_SUPPORTED_SUFFIXES = {".csv", ".tsv", ".xls", ".xlsx"}
_MAX_DATASET_TABLES = 64
_TABLE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")


@dataclass(frozen=True)
class UploadedDatasetTable:
    """One source file or workbook sheet materialized as a SQLite table."""

    source_file: str
    source_sheet: str | None
    table_name: str
    row_count: int
    columns: Tuple[str, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "table_name": self.table_name,
            "row_count": self.row_count,
            "columns": list(self.columns),
        }


def _unique_table_name(raw_name: str, used_names: set[str]) -> str:
    normalized = _TABLE_NAME_RE.sub("_", raw_name).strip("_").casefold()
    if not normalized:
        normalized = "table"
    if normalized[0].isdigit():
        normalized = f"table_{normalized}"
    normalized = normalized[:56]
    candidate = normalized
    counter = 2
    while candidate.casefold() in used_names:
        suffix = f"_{counter}"
        candidate = f"{normalized[: 63 - len(suffix)]}{suffix}"
        counter += 1
    used_names.add(candidate.casefold())
    return candidate


def _read_csv_chunks(path: Path) -> Iterable[Any]:
    import pandas as pd

    separator = "\t" if path.suffix.casefold() == ".tsv" else ","
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            # Validate the whole byte stream before yielding any chunk.  If a
            # decoding error were raised after earlier chunks had already
            # been written, retrying another encoding would duplicate rows.
            with path.open("r", encoding=encoding, newline="") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), ""):
                    if not chunk:
                        break
            reader = pd.read_csv(
                path,
                sep=separator,
                encoding=encoding,
                chunksize=10_000,
                low_memory=False,
            )
            yield from reader
            return
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error


def _write_frame(
    connection: sqlite3.Connection,
    frame: Any,
    table_name: str,
    *,
    if_exists: str,
) -> int:
    # Stable string labels prevent pandas/SQLite from disagreeing about numeric
    # column names while preserving the values themselves.
    frame = frame.copy()
    frame.columns = [str(column) for column in frame.columns]
    # SQLite commonly limits one statement to 999 bound variables.  Keep a
    # little headroom so wide spreadsheets cannot fail merely because pandas
    # uses a multi-row INSERT statement.
    column_count = max(1, len(frame.columns))
    safe_chunk_size = max(1, min(500, 900 // column_count))
    frame.to_sql(
        table_name,
        connection,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=safe_chunk_size,
    )
    return int(len(frame.index))


def _load_csv(
    connection: sqlite3.Connection,
    path: Path,
    table_name: str,
) -> UploadedDatasetTable:
    total_rows = 0
    columns: Tuple[str, ...] = ()
    wrote_table = False
    for frame in _read_csv_chunks(path):
        if not columns:
            columns = tuple(str(column) for column in frame.columns)
        total_rows += _write_frame(
            connection,
            frame,
            table_name,
            if_exists="append" if wrote_table else "replace",
        )
        wrote_table = True
    if not wrote_table:
        raise ValueError(f"Tabular file has no readable rows: {path.name}")
    return UploadedDatasetTable(
        source_file=path.name,
        source_sheet=None,
        table_name=table_name,
        row_count=total_rows,
        columns=columns,
    )


def _load_workbook(
    connection: sqlite3.Connection,
    path: Path,
    used_names: set[str],
) -> List[UploadedDatasetTable]:
    import pandas as pd

    sheets = pd.read_excel(path, sheet_name=None)
    loaded: List[UploadedDatasetTable] = []
    for sheet_name, frame in sheets.items():
        if len(loaded) >= _MAX_DATASET_TABLES:
            raise ValueError(f"Workbook creates more than {_MAX_DATASET_TABLES} tables")
        table_name = _unique_table_name(f"{path.stem}_{sheet_name}", used_names)
        row_count = _write_frame(connection, frame, table_name, if_exists="replace")
        loaded.append(
            UploadedDatasetTable(
                source_file=path.name,
                source_sheet=str(sheet_name),
                table_name=table_name,
                row_count=row_count,
                columns=tuple(str(column) for column in frame.columns),
            )
        )
    if not loaded:
        raise ValueError(f"Workbook contains no readable sheets: {path.name}")
    return loaded


def _candidate_relationships(
    connection: sqlite3.Connection,
    tables: Sequence[UploadedDatasetTable],
) -> List[Dict[str, Any]]:
    """Describe same-named columns; the Agent must still verify cardinality."""

    by_column: Dict[str, List[str]] = {}
    original_names: Dict[Tuple[str, str], str] = {}
    for table in tables:
        for column in table.columns:
            key = column.casefold()
            by_column.setdefault(key, []).append(table.table_name)
            original_names[(table.table_name, key)] = column

    candidates: List[Dict[str, Any]] = []
    for key, table_names in sorted(by_column.items()):
        unique_tables = list(dict.fromkeys(table_names))
        if len(unique_tables) < 2:
            continue
        for left_index, left_table in enumerate(unique_tables[:-1]):
            for right_table in unique_tables[left_index + 1 :]:
                left_column = original_names[(left_table, key)]
                right_column = original_names[(right_table, key)]
                left_quoted = left_column.replace('"', '""')
                right_quoted = right_column.replace('"', '""')
                left_table_quoted = left_table.replace('"', '""')
                right_table_quoted = right_table.replace('"', '""')
                query = f"""
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT "{left_quoted}" AS value
                        FROM "{left_table_quoted}"
                        WHERE "{left_quoted}" IS NOT NULL
                        LIMIT 1000
                    ) AS left_values
                    INNER JOIN (
                        SELECT DISTINCT "{right_quoted}" AS value
                        FROM "{right_table_quoted}"
                        WHERE "{right_quoted}" IS NOT NULL
                        LIMIT 1000
                    ) AS right_values USING (value)
                """
                overlap = int(connection.execute(query).fetchone()[0])
                candidates.append(
                    {
                        "column": left_column,
                        "left_table": left_table,
                        "right_table": right_table,
                        "sample_distinct_overlap": overlap,
                        "status": "candidate_only",
                    }
                )
    return candidates[:256]


def materialize_uploaded_dataset(
    file_paths: Sequence[str],
    database_path: Path,
) -> Tuple[List[UploadedDatasetTable], List[Dict[str, Any]]]:
    """Create a SQLite database without inventing joins or business metrics."""

    if not file_paths:
        raise ValueError("At least one tabular file is required")
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        raise ValueError(f"Dataset database already exists: {database_path.name}")

    used_names: set[str] = set()
    tables: List[UploadedDatasetTable] = []
    connection = sqlite3.connect(str(database_path))
    try:
        for raw_path in file_paths:
            path = Path(raw_path).resolve()
            suffix = path.suffix.casefold()
            if suffix not in _SUPPORTED_SUFFIXES:
                raise ValueError(
                    f"Unsupported tabular file type '{suffix or '(none)'}': {path.name}"
                )
            if suffix in {".csv", ".tsv"}:
                table_name = _unique_table_name(path.stem, used_names)
                tables.append(_load_csv(connection, path, table_name))
            else:
                tables.extend(_load_workbook(connection, path, used_names))
            if len(tables) > _MAX_DATASET_TABLES:
                raise ValueError(
                    f"Dataset creates more than {_MAX_DATASET_TABLES} tables"
                )

        relationships = _candidate_relationships(connection, tables)
        connection.execute(
            """
            CREATE TABLE __dbgpt_dataset_manifest (
                source_file TEXT NOT NULL,
                source_sheet TEXT,
                table_name TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                columns_json TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO __dbgpt_dataset_manifest (
                source_file, source_sheet, table_name, row_count, columns_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    table.source_file,
                    table.source_sheet,
                    table.table_name,
                    table.row_count,
                    json.dumps(list(table.columns), ensure_ascii=False),
                )
                for table in tables
            ],
        )
        connection.execute(
            """
            CREATE TABLE __dbgpt_relationship_candidates (
                column_name TEXT NOT NULL,
                left_table TEXT NOT NULL,
                right_table TEXT NOT NULL,
                sample_distinct_overlap INTEGER NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO __dbgpt_relationship_candidates (
                column_name, left_table, right_table,
                sample_distinct_overlap, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    item["column"],
                    item["left_table"],
                    item["right_table"],
                    item["sample_distinct_overlap"],
                    item["status"],
                )
                for item in relationships
            ],
        )
        connection.commit()
        return tables, relationships
    except Exception:
        connection.rollback()
        connection.close()
        database_path.unlink(missing_ok=True)
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass
