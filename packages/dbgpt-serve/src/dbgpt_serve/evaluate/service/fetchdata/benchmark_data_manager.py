import asyncio
import csv
import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import aiohttp
from sqlalchemy import text

from dbgpt._private.pydantic import BaseModel, ConfigDict
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.configs.model_config import BENCHMARK_DATA_ROOT_PATH
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

logger = logging.getLogger(__name__)

BENCHMARK_DEFAULT_DB_SCHEMA = "ant_icube_dev."


class BenchmarkDataConfig(BaseModel):
    """Configuration for Benchmark Data Manager"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cache_dir: str = "cache"
    db_path: str = os.path.join(
        BENCHMARK_DATA_ROOT_PATH, f"{BENCHMARK_DEFAULT_DB_SCHEMA}db"
    )
    table_mapping_file: str = os.path.join(
        BENCHMARK_DATA_ROOT_PATH, "table_mapping.json"
    )
    cache_expiry_days: int = 1
    repo_url: str = "https://github.com/eosphoros-ai/Falcon"
    data_dir: str = "data/source"


class BenchmarkDataManager(BaseComponent):
    """Manage benchmark data lifecycle including fetching, transformation and storage"""

    name = ComponentType.BENCHMARK_DATA_MANAGER

    def __init__(
        self, system_app: SystemApp, config: Optional[BenchmarkDataConfig] = None
    ):
        super().__init__(system_app)
        self._config = config or BenchmarkDataConfig()
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[SQLiteConnector] = None
        self._table_mappings = self._load_mappings()
        self._lock = asyncio.Lock()
        self.temp_dir: Optional[str] = None

        # Ensure directories exist
        os.makedirs(self._config.cache_dir, exist_ok=True)
        db_dir = os.path.dirname(self._config.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._startup_loaded: bool = False

    def init_app(self, system_app: SystemApp):
        """Initialize the AgentManager."""
        self.system_app = system_app

    async def async_before_stop(self):
        try:
            logger.info("BenchmarkDataManager: closing resources before stop...")
            await self.close()
            logger.info("BenchmarkDataManager: close done.")
        except Exception as e:
            logger.warning(f"BenchmarkDataManager: close failed: {e}")

    async def __aenter__(self):
        self._http_session = aiohttp.ClientSession()
        await self.init_connector()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def get_connector(self):
        return self._connector

    async def init_connector(self):
        """Initialize SQLiteConnector"""
        async with self._lock:
            if not self._connector:
                self._connector = SQLiteConnector.from_file_path(self._config.db_path)

    async def close_connector(self):
        """Close SQLiteConnector"""
        async with self._lock:
            if self._connector:
                try:
                    self._connector.close()
                except Exception as e:
                    logger.warning(f"Close connector failed: {e}")
                self._connector = None

    async def close(self):
        """Clean up resources"""
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        await self.close_connector()
        self._cleanup_temp_dir()

    async def _run_in_thread(self, func, *args, **kwargs):
        """Run blocking function in thread to avoid blocking event loop"""
        return await asyncio.to_thread(func, *args, **kwargs)

    async def load_data(self):
        logger.info("BenchmarkDataManager: start load_data.")

        try:
            if not self._config.repo_url:
                logger.info("BenchmarkDataManager: repo_url not set, skip auto load.")
                return

            if self._startup_loaded:
                logger.info("BenchmarkDataManager: already loaded on startup, skip.")
                return

            logger.info(
                f"BenchmarkDataManager: auto loading repo {self._config.repo_url} "
                f"dir={self._config.data_dir}"
            )
            await get_benchmark_manager(self.system_app).load_from_github(
                repo_url=self._config.repo_url, data_dir=self._config.data_dir
            )
            self._startup_loaded = True
            logger.info("BenchmarkDataManager: auto load finished.")
        except Exception as e:
            logger.error(f"BenchmarkDataManager: auto load failed: {e}")

    def _sanitize_column_name(self, name: str) -> str:
        if name is None:
            return ""
        name = str(name).strip().strip('"').strip("'")
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
            "\t",
            "\r",
            "\n",
            "\x00",
        ]
        while name and name[-1] in invalid_chars:
            name = name[:-1]
        for ch in invalid_chars:
            if ch in name:
                name = name.replace(ch, "_")
        while "__" in name:
            name = name.replace("__", "_")
        if name and not (name[0].isalpha() or name[0] == "_"):
            name = "_" + name
        return name.lower()

    def _sanitize_and_dedup_headers(self, headers: List[str]) -> List[str]:
        sanitized: List[str] = []
        used: set = set()
        for idx, h in enumerate(headers):
            name = self._sanitize_column_name(h)
            if not name:
                name = f"col_{idx}"
            base = name
            k = 2
            while name in used or not name:
                name = f"{base}_{k}"
                k += 1
            used.add(name)
            sanitized.append(name)
        return sanitized

    # ==========================================================

    # 通用查询（阻塞实现，在线程池中调用，支持超时与可中断）
    def _query_blocking(
        self, sql: str, params: Optional[Any] = None, timeout: Optional[float] = None
    ):
        assert self._connector is not None, "Connector not initialized"

        # 结果容器与同步事件
        result: Dict[str, Any] = {"data": None, "error": None}
        done_event = threading.Event()
        cancel_event = threading.Event()

        def _execute_query():
            dbapi_conn = None
            progress_installed = False
            try:
                with self._connector.session_scope() as session:
                    # SQLite 下安装 progress handler，以便在取消时中断执行
                    try:
                        if getattr(self._connector, "dialect", None) == "sqlite":
                            conn = session.connection()
                            dbapi_conn = getattr(conn, "connection", None)
                            if dbapi_conn is not None and hasattr(
                                dbapi_conn, "set_progress_handler"
                            ):

                                def _progress_handler():
                                    # 置位取消后返回非零，中断当前语句
                                    return 1 if cancel_event.is_set() else 0

                                dbapi_conn.set_progress_handler(
                                    _progress_handler, 10000
                                )
                                progress_installed = True
                    except Exception:
                        # 安装失败则忽略，回退为不可中断
                        progress_installed = False

                    # 执行查询（保持对 tuple/dict 参数的兼容）
                    if isinstance(params, tuple):
                        cursor = session.execute(text(sql), params)
                    else:
                        cursor = session.execute(text(sql), params or {})

                    if cursor.returns_rows:
                        rows = cursor.fetchall()
                        cols = list(cursor.keys())
                        result["data"] = (cols, rows)
                    else:
                        result["data"] = ([], [])
            except Exception as e:
                result["error"] = e
            finally:
                # 清理 progress handler，避免影响连接的后续使用
                if progress_installed and dbapi_conn is not None:
                    try:
                        dbapi_conn.set_progress_handler(None, 0)
                    except Exception:
                        pass
                done_event.set()

        # 启动查询线程（daemon=True确保程序可以正常退出）
        thread = threading.Thread(target=_execute_query, daemon=True)
        thread.start()

        # 等待查询完成或超时
        if timeout is None:
            done_event.wait()
        else:
            if not done_event.wait(timeout=timeout):
                # 触发取消标记，要求后台线程尽快中断
                cancel_event.set()
                # 尽力等待子线程尽快退出，避免成为“僵尸线程”
                thread.join(timeout=2.0)
                raise TimeoutError(f"Sql query exceeded timeout of {timeout} seconds")

        if result["error"] is not None:
            raise result["error"]
        return cast(Tuple[List[str], List[Tuple]], result["data"])

    # 通用写入（阻塞实现，在线程池中调用）
    def _execute_blocking(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ):
        assert self._connector is not None, "Connector not initialized"

        def _execute_write():
            with self._connector.session_scope() as session:
                result = session.execute(text(sql), params or {})
                session.commit()
                return result.rowcount

        if timeout is not None:
            # 使用ThreadPoolExecutor实现超时控制，类似于基类中DuckDB的实现
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_execute_write)
                try:
                    return future.result(timeout=timeout)
                except FutureTimeoutError:
                    raise TimeoutError(
                        f"Sql Execute exceeded timeout of {timeout} seconds"
                    )
        else:
            return _execute_write()

    async def query(
        self, query: str, params: tuple = (), timeout: Optional[float] = None
    ) -> List[Dict]:
        """Execute query and return results as dict list

        Args:
            query: SQL query string
            params: Query parameters
            timeout: Query timeout in seconds (optional)
        """
        await self.init_connector()
        cols, rows = await self._run_in_thread(
            self._query_blocking, query, params, timeout
        )
        return [dict(zip(cols, row)) for row in rows]

    async def load_from_github(
        self, repo_url: str, data_dir: str = "data/source"
    ) -> Dict:
        """Main method to load data from GitHub repository"""
        try:
            await self.init_connector()

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
            raise RuntimeError(f"Benchmark data loading failed: {e}") from e
        finally:
            self._cleanup_temp_dir()

    async def get_table_info(self) -> Dict:
        """Get metadata about all tables"""
        await self.init_connector()
        assert self._connector is not None

        def _work():
            with self._connector.session_scope() as session:
                tables = session.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                tables = [row[0] for row in tables.fetchall()]
                result: Dict[str, Any] = {}
                for table_name in tables:
                    row_count = session.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}"')
                    ).fetchone()[0]
                    columns = session.execute(
                        text(f'PRAGMA table_info("{table_name}")')
                    ).fetchall()
                    result[table_name] = {
                        "row_count": row_count,
                        "columns": [
                            {"name": col[1], "type": col[2]} for col in columns
                        ],
                    }
                return result

        return await self._run_in_thread(_work)

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
        if mapped_name is None:
            mapped_name = name or ""

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
        while mapped_name and mapped_name[-1] in invalid_chars:
            mapped_name = mapped_name[:-1]
        for char in invalid_chars:
            if char in mapped_name:
                mapped_name = mapped_name.replace(char, "_")
        while "__" in mapped_name:
            mapped_name = mapped_name.replace("__", "_")

        return (mapped_name or "").lower()

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
            if self._http_session is None:
                self._http_session = aiohttp.ClientSession()
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
            raise RuntimeError(f"Failed to download repository: {str(e)}") from e

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
        await self.init_connector()
        assert self._connector is not None
        results = {
            "total_files": len(csv_files),
            "successful": 0,
            "failed": 0,
            "tables_created": [],
        }

        def _process_one_file(file_info: Dict) -> Tuple[bool, Optional[str]]:
            table_name = ""
            try:
                path_parts = [p for p in file_info["rel_path"].split(os.sep) if p]
                table_name = "_".join(path_parts + [Path(file_info["file_name"]).stem])
                table_name = self._sanitize_table_name(table_name)

                with self._connector.session_scope() as session:
                    session.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                    session.commit()
                encodings = ["utf-8-sig", "utf-8", "latin-1", "iso-8859-1", "cp1252"]

                for encoding in encodings:
                    try:
                        with open(file_info["full_path"], "r", encoding=encoding) as f:
                            content = f.read()

                        if not content.strip():
                            raise ValueError("File is empty")

                        content = content.replace("\r\n", "\n").replace("\r", "\n")
                        lines = [line for line in content.split("\n") if line.strip()]
                        if not lines:
                            raise ValueError("No data after normalization")

                        header_line = lines[0]
                        data_line = lines[1] if len(lines) > 1 else ""

                        try:
                            sample_for_sniff = "\n".join(lines[:10])
                            sniffer = csv.Sniffer()
                            try:
                                dialect = sniffer.sniff(sample_for_sniff)
                            except Exception:
                                # Fallback: choose delimiter by counting common
                                # separators in header/data line
                                delims = [",", "\t", ";", "|"]
                                counts = {
                                    d: (header_line.count(d) if header_line else 0)
                                    + (data_line.count(d) if data_line else 0)
                                    for d in delims
                                }
                                best = (
                                    max(counts, key=counts.get)
                                    if any(counts.values())
                                    else ","
                                )

                                class _DefaultDialect(csv.Dialect):
                                    delimiter = best
                                    quotechar = '"'
                                    doublequote = True
                                    skipinitialspace = False
                                    lineterminator = "\n"
                                    quoting = csv.QUOTE_MINIMAL

                                dialect = _DefaultDialect()

                            try:
                                has_header = sniffer.has_header("\n".join(lines[:50]))
                            except Exception:
                                has_header = True

                            header_row = (
                                list(csv.reader([header_line], dialect))[0]
                                if header_line
                                else []
                            )
                            first_data_row = (
                                list(csv.reader([data_line], dialect))[0]
                                if data_line
                                else []
                            )

                            # Heuristic: if has_header is False but header_row looks
                            # like names (mostly alphabetic), treat as header
                            if not has_header:

                                def _looks_like_header(tokens: List[str]) -> bool:
                                    if not tokens:
                                        return False
                                    # 非空、重复少、字母比例高
                                    cleaned = [
                                        str(t).strip() for t in tokens if str(t).strip()
                                    ]
                                    if not cleaned:
                                        return False
                                    # 允许少量数字，但大多以字母开头
                                    alpha_starts = sum(
                                        1
                                        for t in cleaned
                                        if t and (t[0].isalpha() or t[0] == "_")
                                    )
                                    return alpha_starts >= max(
                                        1, int(0.6 * len(cleaned))
                                    )

                                if _looks_like_header(header_row):
                                    has_header = True

                            if not has_header:
                                num_cols_guess = len(header_row)
                                headers = [f"col_{i}" for i in range(num_cols_guess)]
                                first_data_row = header_row
                            else:
                                headers = header_row

                            num_cols = (
                                len(first_data_row) if first_data_row else len(headers)
                            )

                            # no header
                            if not headers or all(
                                (not str(h).strip()) for h in headers
                            ):
                                headers = [f"col_{i}" for i in range(num_cols or 1)]

                            headers = self._sanitize_and_dedup_headers(headers)

                            if num_cols <= 0:
                                num_cols = len(headers)
                            headers = headers[:num_cols]
                            if not headers or any(
                                h is None or h == "" for h in headers
                            ):
                                raise csv.Error("Invalid headers after sanitization")

                            create_sql = f'''
                                CREATE TABLE IF NOT EXISTS "{table_name}" (
                                    {", ".join([f'"{h}" TEXT' for h in headers])}
                                )
                            '''
                            insert_sql = f'''
                                INSERT INTO "{table_name}" ({
                                ", ".join([f'"{h}"' for h in headers])
                            })
                                VALUES ({
                                ", ".join([":" + f"p{i}" for i in range(len(headers))])
                            })
                            '''

                            with self._connector.session_scope() as session:
                                logger.debug(
                                    f"Table: {table_name}, headers(final): {headers}"
                                )
                                session.execute(text(create_sql))

                                reader = csv.reader(lines, dialect)
                                if has_header:
                                    next(reader, None)

                                batch_params: List[Dict[str, Any]] = []
                                for row in reader:
                                    if not row:
                                        continue
                                    if len(row) != len(headers):
                                        if len(row) < len(headers):
                                            row += [None] * (len(headers) - len(row))
                                        else:
                                            row = row[: len(headers)]
                                    params = {
                                        f"p{i}": (row[i] if i < len(row) else None)
                                        for i in range(len(headers))
                                    }
                                    batch_params.append(params)
                                    if len(batch_params) >= 1000:
                                        session.execute(text(insert_sql), batch_params)
                                        batch_params = []
                                if batch_params:
                                    session.execute(text(insert_sql), batch_params)
                                session.commit()

                            return True, table_name

                        except csv.Error:
                            self._import_with_simple_split_blocking(table_name, content)
                            return True, table_name

                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        logger.warning(f"Error with encoding {encoding}: {str(e)}")
                        continue

                try:
                    with open(file_info["full_path"], "rb") as f:
                        content = f.read().decode("ascii", errors="ignore")
                        if content.strip():
                            self._import_with_simple_split_blocking(table_name, content)
                            return True, table_name
                        else:
                            raise ValueError("File is empty or unreadable")
                except Exception as e:
                    return (
                        False,
                        f"Failed to process {file_info['file_name']}: {str(e)}",
                    )

            except Exception as e:
                return (
                    False,
                    f"Failed to process {file_info.get('full_path', '')}: {str(e)}",
                )

        for file_info in csv_files:
            ok, info = await self._run_in_thread(_process_one_file, file_info)
            if ok:
                results["successful"] += 1
                if info:
                    results["tables_created"].append(info)
            else:
                results["failed"] += 1
                logger.error(info)

        return results

    def _import_with_simple_split_blocking(self, table_name: str, content: str):
        """Fallback method for malformed CSV files (blocking, 使用 SQLAlchemy 执行)"""
        assert self._connector is not None
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line for line in content.split("\n") if line.strip()]
        if not lines:
            raise ValueError("No data found after cleaning")

        first_line = lines[0]
        delimiter = "," if "," in first_line else "\t" if "\t" in first_line else ";"

        raw_headers = first_line.split(delimiter)
        headers = self._sanitize_and_dedup_headers(raw_headers)
        actual_columns = len(headers)

        create_sql = f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                {", ".join([f'"{h}" TEXT' for h in headers])}
            )
        """

        insert_sql = f"""
            INSERT INTO "{table_name}" ({", ".join([f'"{h}"' for h in headers])})
            VALUES ({", ".join([":" + f"p{i}" for i in range(actual_columns)])})
        """

        with self._connector.session_scope() as session:
            session.execute(text(create_sql))
            batch: List[Dict[str, Any]] = []
            for line in lines[1:]:
                row = line.split(delimiter)
                if len(row) != actual_columns:
                    if len(row) < actual_columns:
                        row += [None] * (actual_columns - len(row))
                    else:
                        row = row[:actual_columns]
                params = {f"p{i}": row[i] for i in range(actual_columns)}
                batch.append(params)
                if len(batch) >= 1000:
                    session.execute(text(insert_sql), batch)
                    batch = []
            if batch:
                session.execute(text(insert_sql), batch)
            session.commit()

    async def get_table_info_simple(self) -> List[str]:
        """Return simplified table info: table(column1,column2,...)"""
        await self.init_connector()
        assert self._connector is not None

        def _work():
            return list(self._connector.table_simple_info())

        return await self._run_in_thread(_work)

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
    app = system_app or _SYSTEM_APP
    return BenchmarkDataManager.get_instance(cast(SystemApp, app))
