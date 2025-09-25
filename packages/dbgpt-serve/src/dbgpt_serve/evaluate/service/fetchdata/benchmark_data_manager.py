import asyncio
import csv
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import aiohttp

from dbgpt._private.pydantic import BaseModel, ConfigDict
from dbgpt.component import BaseComponent, ComponentType, SystemApp

logger = logging.getLogger(__name__)


class BenchmarkDataConfig(BaseModel):
    """Configuration for Benchmark Data Manager"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cache_dir: str = "cache"
    db_path: str = "benchmark_data.db"
    table_mapping_file: Optional[str] = None
    cache_expiry_days: int = 1


class BenchmarkDataManager(BaseComponent):
    """Manage benchmark data lifecycle including fetching, transformation and storage"""

    name = ComponentType.BENCHMARK_DATA_MANAGER

    def __init__(
        self, system_app: SystemApp, config: Optional[BenchmarkDataConfig] = None
    ):
        super().__init__(system_app)
        self._config = config or BenchmarkDataConfig()
        self._http_session = None
        self._db_conn = None
        self._table_mappings = self._load_mappings()
        self._lock = asyncio.Lock()
        self.temp_dir = None

        # Ensure directories exist
        os.makedirs(self._config.cache_dir, exist_ok=True)

    def init_app(self, system_app: SystemApp):
        """Initialize the AgentManager."""
        self.system_app = system_app

    async def __aenter__(self):
        self._http_session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """Clean up resources"""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None
        self._cleanup_temp_dir()

    async def get_connection(self) -> sqlite3.Connection:
        """Get database connection (thread-safe)"""
        async with self._lock:
            if not self._db_conn:
                self._db_conn = sqlite3.connect(self._config.db_path)
            return self._db_conn

    async def query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return results as dict list"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    async def load_from_github(
        self, repo_url: str, data_dir: str = "data/source"
    ) -> Dict:
        """Main method to load data from GitHub repository"""
        try:
            # 1. Download or use cached repository
            repo_dir = await self._download_repo_contents(repo_url)

            # 2. Find all CSV files recursively
            csv_files = self._discover_csv_files(repo_dir, data_dir)
            if not csv_files:
                raise ValueError("No CSV files found")
            logger.info(f"Found {len(csv_files)} CSV files")

            # 3. Import to SQLite
            result = await self._import_to_database(csv_files)
            return result

        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            raise
        finally:
            self._cleanup_temp_dir()

    async def get_table_info(self) -> Dict:
        """Get metadata about all tables"""
        conn = await self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        result = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            result[table_name] = {
                "row_count": row_count,
                "columns": [{"name": col[1], "type": col[2]} for col in columns],
            }
        return result

    def clear_cache(self):
        """Clear cached repository files"""
        try:
            for filename in os.listdir(self._config.cache_dir):
                file_path = os.path.join(self._config.cache_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Failed to delete {file_path}: {str(e)}")
            logger.info("Cache cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear cache: {str(e)}")

    def _load_mappings(self) -> Dict[str, str]:
        """Load table name mappings from config file"""
        if not self._config.table_mapping_file or not os.path.exists(
            self._config.table_mapping_file
        ):
            logger.warning(
                f"Table mapping file not found: {self._config.table_mapping_file}"
            )
            return {}

        try:
            with open(self._config.table_mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                return {
                    key: value.split(".")[-1] if "." in value else value
                    for key, value in mapping.items()
                }
        except Exception as e:
            logger.error(f"Failed to load table mapping: {str(e)}")
            return {}

    def _sanitize_table_name(self, name: str) -> str:
        """Normalize table names using mappings"""
        mapped_name = self._table_mappings.get(name.lower(), name)

        # Clean special characters
        invalid_chars = [
            "-",
            " ",
            ".",
            ",",
            ";",
            ":",
            "!",
            "?",
            "'",
            '"',
            "(",
            ")",
            "[",
            "]",
            "{",
            "}",
        ]
        for char in invalid_chars:
            mapped_name = mapped_name.replace(char, "_")
        while "__" in mapped_name:
            mapped_name = mapped_name.replace("__", "_")

        return mapped_name.lower()

    async def _download_repo_contents(self, repo_url: str) -> str:
        """Download repository with caching"""
        cache_path = self._get_cache_path(repo_url)

        # Use cache if valid
        if os.path.exists(cache_path) and self._is_cache_valid(cache_path):
            logger.info(f"Using cached repository: {cache_path}")
            return self._extract_cache(cache_path)

        # Download fresh copy
        self.temp_dir = tempfile.mkdtemp()
        zip_url = (
            repo_url.replace("github.com", "api.github.com/repos") + "/zipball/main"
        )
        logger.info(f"Downloading from GitHub repo: {zip_url}")

        try:
            async with self._http_session.get(zip_url) as response:
                response.raise_for_status()
                zip_path = os.path.join(self.temp_dir, "repo.zip")

                with open(zip_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)

                # Cache the download
                shutil.copy2(zip_path, cache_path)
                logger.info(f"Saved repository to cache: {cache_path}")

                return self._extract_zip(zip_path)

        except Exception as e:
            self._cleanup_temp_dir()
            raise RuntimeError(f"Failed to download repository: {str(e)}")

    def _get_cache_path(self, repo_url: str) -> str:
        """Get path to cached zip file"""
        cache_key = hashlib.md5(repo_url.encode("utf-8")).hexdigest()
        return os.path.join(self._config.cache_dir, f"{cache_key}.zip")

    def _is_cache_valid(self, cache_path: str) -> bool:
        """Check if cache is still valid"""
        if not os.path.exists(cache_path):
            return False
        file_age = time.time() - os.path.getmtime(cache_path)
        return file_age < (self._config.cache_expiry_days * 24 * 60 * 60)

    def _extract_cache(self, cache_path: str) -> str:
        """Extract cached repository"""
        self.temp_dir = tempfile.mkdtemp()
        return self._extract_zip(cache_path)

    def _extract_zip(self, zip_path: str) -> str:
        """Extract zip to temp directory"""
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(self.temp_dir)

        extracted_dirs = [
            d
            for d in os.listdir(self.temp_dir)
            if os.path.isdir(os.path.join(self.temp_dir, d))
        ]
        if not extracted_dirs:
            raise ValueError("No valid directory found after extraction")
        return os.path.join(self.temp_dir, extracted_dirs[0])

    def _discover_csv_files(self, base_dir: str, search_dir: str) -> List[Dict]:
        """Find all CSV files recursively"""
        full_search_dir = os.path.join(base_dir, search_dir) if search_dir else base_dir
        if not os.path.exists(full_search_dir):
            raise ValueError(f"Directory not found: {full_search_dir}")

        csv_files = []
        for root, _, files in os.walk(full_search_dir):
            for file in files:
                if file.lower().endswith(".csv"):
                    rel_path = os.path.relpath(root, start=base_dir)
                    csv_files.append(
                        {
                            "full_path": os.path.join(root, file),
                            "rel_path": rel_path,
                            "file_name": file,
                        }
                    )
        return csv_files

    async def _import_to_database(self, csv_files: List[Dict]) -> Dict:
        """Import CSV data to SQLite"""
        conn = await self.get_connection()
        cursor = conn.cursor()
        results = {
            "total_files": len(csv_files),
            "successful": 0,
            "failed": 0,
            "tables_created": [],
        }

        for file_info in csv_files:
            try:
                path_parts = [p for p in file_info["rel_path"].split(os.sep) if p]
                table_name = "_".join(path_parts + [Path(file_info["file_name"]).stem])
                table_name = self._sanitize_table_name(table_name)

                # Try multiple encodings
                encodings = ["utf-8-sig", "utf-8", "latin-1", "iso-8859-1", "cp1252"]

                for encoding in encodings:
                    try:
                        with open(file_info["full_path"], "r", encoding=encoding) as f:
                            content = f.read()

                            # Handle empty files
                            if not content.strip():
                                raise ValueError("File is empty")

                            # Replace problematic line breaks if needed
                            content = content.replace("\r\n", "\n").replace("\r", "\n")

                            # Split into lines
                            lines = [
                                line for line in content.split("\n") if line.strip()
                            ]

                            try:
                                header_line = lines[0]
                                data_line = lines[1] if len(lines) > 1 else ""

                                # Detect delimiter (comma, semicolon, tab)
                                sniffer = csv.Sniffer()
                                dialect = sniffer.sniff(header_line)
                                has_header = sniffer.has_header(content[:1024])

                                if has_header:
                                    headers = list(csv.reader([header_line], dialect))[
                                        0
                                    ]
                                    first_data_row = (
                                        list(csv.reader([data_line], dialect))[0]
                                        if data_line
                                        else []
                                    )
                                else:
                                    headers = list(csv.reader([header_line], dialect))[
                                        0
                                    ]
                                    first_data_row = headers  # first line is data
                                    headers = [f"col_{i}" for i in range(len(headers))]

                                # Determine actual number of columns from data
                                actual_columns = (
                                    len(first_data_row)
                                    if first_data_row
                                    else len(headers)
                                )

                                # Create table with correct number of columns
                                create_sql = f"""
                                CREATE TABLE IF NOT EXISTS {table_name} ({
                                    ", ".join(
                                        [
                                            f'"{h}" TEXT'
                                            for h in headers[:actual_columns]
                                        ]
                                    )
                                })
                                """
                                cursor.execute(create_sql)

                                # Prepare insert statement
                                insert_sql = f"""
                                INSERT INTO {table_name} VALUES ({
                                    ", ".join(["?"] * actual_columns)
                                })
                                """

                                # Process data
                                batch = []
                                reader = csv.reader(lines, dialect)
                                if has_header:
                                    next(reader)  # skip header

                                for row in reader:
                                    if not row:  # skip empty rows
                                        continue

                                    # Ensure row has correct number of columns
                                    if len(row) != actual_columns:
                                        if len(row) < actual_columns:
                                            row += [None] * (actual_columns - len(row))
                                        else:
                                            row = row[:actual_columns]

                                    batch.append(row)
                                    if len(batch) >= 1000:
                                        cursor.executemany(insert_sql, batch)
                                        batch = []

                                if batch:
                                    cursor.executemany(insert_sql, batch)

                                results["successful"] += 1
                                results["tables_created"].append(table_name)
                                break

                            except csv.Error as e:
                                # Fallback for malformed CSV files
                                self._import_with_simple_split(
                                    cursor, table_name, content, results, file_info
                                )
                                break

                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        logger.warning(f"Error with encoding {encoding}: {str(e)}")
                        continue
                else:
                    # All encodings failed - try binary mode as last resort
                    try:
                        with open(file_info["full_path"], "rb") as f:
                            content = f.read().decode("ascii", errors="ignore")
                            if content.strip():
                                self._import_with_simple_split(
                                    cursor, table_name, content, results, file_info
                                )
                            else:
                                raise ValueError("File is empty or unreadable")
                    except Exception as e:
                        results["failed"] += 1
                        logger.error(
                            f"Failed to process {file_info['file_name']}: {str(e)}"
                        )

            except Exception as e:
                results["failed"] += 1
                logger.error(f"Failed to process {file_info['full_path']}: {str(e)}")

        self._db_conn.commit()
        return results

    def _import_with_simple_split(
        self, cursor, table_name, content, results, file_info
    ):
        """Fallback method for malformed CSV files"""
        # Normalize line endings
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line for line in content.split("\n") if line.strip()]

        if not lines:
            raise ValueError("No data found after cleaning")

        # Determine delimiter
        first_line = lines[0]
        delimiter = "," if "," in first_line else "\t" if "\t" in first_line else ";"

        # Process header
        headers = first_line.split(delimiter)
        actual_columns = len(headers)

        # Create table
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {", ".join([f"col_{i} TEXT" for i in range(actual_columns)])}
        )
        """
        cursor.execute(create_sql)

        # Prepare insert
        insert_sql = f"""
        INSERT INTO {table_name} VALUES ({", ".join(["?"] * actual_columns)})
        """

        # Process data
        batch = []
        for line in lines[1:]:  # skip header
            row = line.split(delimiter)
            if len(row) != actual_columns:
                if len(row) < actual_columns:
                    row += [None] * (actual_columns - len(row))
                else:
                    row = row[:actual_columns]
            batch.append(row)

            if len(batch) >= 1000:
                cursor.executemany(insert_sql, batch)
                batch = []

        if batch:
            cursor.executemany(insert_sql, batch)

        results["successful"] += 1
        results["tables_created"].append(table_name)

    def _cleanup_temp_dir(self):
        """Clean up temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            except Exception as e:
                logger.warning(f"Failed to clean temp dir: {str(e)}")


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_benchmark_data(
    system_app: SystemApp, config: Optional[BenchmarkDataConfig] = None
):
    """Initialize benchmark data manager component"""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    manager = BenchmarkDataManager(system_app, config)
    system_app.register_instance(manager)
    return manager


def get_benchmark_manager(
    system_app: Optional[SystemApp] = None,
) -> BenchmarkDataManager:
    """Get the benchmark data manager instance"""
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_benchmark_data(system_app)
    return BenchmarkDataManager.get_instance(system_app)
