import asyncio
import csv
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast, Literal

import aiohttp
from sqlalchemy import text

from dbgpt._private.pydantic import BaseModel, ConfigDict
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.configs.model_config import BENCHMARK_DATA_ROOT_PATH
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

logger = logging.getLogger(__name__)

# ---- Unified model result definitions for load_file_from_github ----
class FailureDetail(BaseModel):
    line_no: int
    error: str
    line: str

class Row(BaseModel):
    line_no: int
    data: Any

class FileLoadResult(BaseModel):
    type: Literal["jsonl", "json", "text"]
    file_path: str
    file_name: str
    encoding: Optional[str] = None
    rows: List[Row]
    count: int
    failed_count: int
    failures: List[FailureDetail] = []


class SqlFileItem(BaseModel):
    """Represents a single SQL file with its ID and content"""

    sql_id: str
    sql_content: str
    file_path: str
    file_name: str
    encoding: Optional[str] = None


class GoldenSqlListResult(BaseModel):
    """Result object for golden SQL list loading

    Provides efficient lookup by SQL ID with dict-like interface.
    """
    sql_items: Dict[str, SqlFileItem]
    total_count: int
    failed_count: int

    def get_by_id(self, sql_id: str) -> Optional[SqlFileItem]:
        """Get SQL item by ID

        Args:
            sql_id: The SQL file ID (filename prefix without extension)

        Returns:
            SqlFileItem if found, None otherwise
        """
        return self.sql_items.get(sql_id)

    def get_sql_content(self, sql_id: str) -> Optional[str]:
        """Get SQL content by ID

        Args:
            sql_id: The SQL file ID (filename prefix without extension)

        Returns:
            SQL content string if found, None otherwise
        """
        item = self.sql_items.get(sql_id)
        return item.sql_content if item else None

    def list_all_ids(self) -> List[str]:
        """Get list of all SQL IDs

        Returns:
            List of SQL IDs sorted alphabetically
        """
        return sorted(self.sql_items.keys())

    def __len__(self) -> int:
        """Return number of successfully loaded SQL files"""
        return len(self.sql_items)

    def __contains__(self, sql_id: str) -> bool:
        """Check if SQL ID exists"""
        return sql_id in self.sql_items

    def __iter__(self):
        """Iterate over SQL items"""
        return iter(self.sql_items.values())


BENCHMARK_DEFAULT_DB_SCHEMA = "ant_icube_dev."


class BenchmarkDataConfig(BaseModel):
    """Configuration for Benchmark Data Manager"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cache_dir: str = "cache"
    db_path: str = os.path.join(
        BENCHMARK_DATA_ROOT_PATH, f"{BENCHMARK_DEFAULT_DB_SCHEMA}db"
    )
    table_mapping_file: Optional[str] = None
    cache_expiry_days: int = 1
    repo_url: str = "https://github.com/eosphoros-ai/Falcon"
    data_dirs: List[str] = ["dev_data/dev_databases", "test_data/dev_databases"]


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
            await self.close()
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
                f"dirs={self._config.data_dirs}"
            )
            await get_benchmark_manager(self.system_app).load_from_github(
                repo_url=self._config.repo_url, data_dirs=self._config.data_dirs
            )
            self._startup_loaded = True
            logger.info("BenchmarkDataManager: auto load finished.")
        except Exception as e:
            logger.error(f"BenchmarkDataManager: auto load failed: {e}")

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
            self,
            repo_url: str,
            data_dirs: List[str] = ["dev_data/dev_databases", "test_data/dev_databases"],
    ) -> Dict:
        """Main method to load data from GitHub repository"""
        try:
            await self.init_connector()

            # 1. Download or use cached repository
            repo_dir = await self._download_repo_contents(repo_url)

            # 2. Find all SQLite files recursively in the specified data_dirs
            all_sqlite_files = []
            for d_dir in data_dirs:
                try:
                    files = self._discover_sqlite_files(repo_dir, d_dir)
                    logger.info(f"Found {len(files)} SQLite files in {d_dir}")
                    all_sqlite_files.extend(files)
                except ValueError as ve:
                    # 如果某个目录不存在，记录警告但不中断整个流程
                    logger.warning(f"Skip directory {d_dir}: {ve}")

            if not all_sqlite_files:
                raise ValueError(
                    f"No SQLite files found in any of the directories: {data_dirs}"
                )

            logger.info(f"Total SQLite files to merge: {len(all_sqlite_files)}")

            # 3. Merge all SQLite files into the main database
            result = await self._merge_sqlite_databases(all_sqlite_files)
            return result

        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            raise RuntimeError(f"Benchmark data loading failed: {e}") from e
        finally:
            self._cleanup_temp_dir()

    async def load_file_from_github(self, file_name: Optional[str] = None
    ) -> Optional[FileLoadResult]:
        """Download and read a specified file from a GitHub repository.

        Supported file types: .json / .jsonl
        `file_name` can be a relative path within the repository or a plain filename (will be searched recursively).

        Unified return structure (FileLoadResult):
          - type: "json" | "jsonl"
          - file_path, file_name, encoding
          - rows: List[{line_no:int, data:Any}] where data is parsed JSON object
          - count: total number of rows
          - failed_count: number of failed lines (non-zero for jsonl or malformed json)
          - failures: details for failed lines

        For JSON files:
          - If the file contains a JSON array, each element becomes a Row
          - If the file contains a single JSON object, it becomes one Row
          - The structure is flexible and doesn't depend on specific keys
        """
        try:
            if not file_name or not str(file_name).strip():
                return None

            # Download or use cached repository
            repo_dir = await self._download_repo_contents(self._config.repo_url)

            # Allowed file extensions
            allowed_exts = {".jsonl", ".json"}

            # Pre-check extension of `file_name` (if provided), otherwise filter by allowed list later
            _, requested_ext = os.path.splitext(str(file_name).lower())
            if requested_ext and requested_ext not in allowed_exts:
                raise ValueError(f"Unsupported file type: {requested_ext}")

            # Handle both relative path and plain filename cases
            normalized = str(file_name).strip().lstrip("/").replace("\\", os.sep)
            candidate_paths: List[str] = []

            # Prefer direct path resolution using the relative path
            direct_path = os.path.join(repo_dir, normalized)
            if os.path.isfile(direct_path):
                ext = os.path.splitext(direct_path.lower())[1]
                if not requested_ext:
                    if ext in allowed_exts:
                        candidate_paths.append(direct_path)
                elif ext == requested_ext:
                    candidate_paths.append(direct_path)

            # If not found, recursively search by filename match
            if not candidate_paths:
                target_name = os.path.basename(normalized)
                for root, _, files in os.walk(repo_dir):
                    for f in files:
                        if f == target_name:
                            full = os.path.join(root, f)
                            ext = os.path.splitext(f.lower())[1]
                            if not requested_ext:
                                if ext in allowed_exts:
                                    candidate_paths.append(full)
                            elif ext == requested_ext:
                                candidate_paths.append(full)

            if not candidate_paths:
                raise FileNotFoundError(f"File not found: {file_name}")

            # Choose a stable candidate (sorted by path length and lexicographical order)
            chosen = sorted(candidate_paths, key=lambda p: (len(p), p))[0]
            chosen_ext = os.path.splitext(chosen.lower())[1]

            # Build repository-relative path for the file (avoid returning temp local path)
            rel_path = os.path.relpath(chosen, repo_dir)
            rel_path_posix = rel_path.replace(os.sep, "/")

            # Try multiple encodings
            encodings = ["utf-8", "iso-8859-1"]

            # Handle .json files (array or single object)
            if chosen_ext == ".json":
                return await self._parse_json_file(
                    chosen, rel_path_posix, encodings
                )
            
            # Handle .jsonl files (line-delimited JSON)
            elif chosen_ext == ".jsonl":
                return await self._parse_jsonl_file(
                    chosen, rel_path_posix, encodings
                )
            
            else:
                raise ValueError(f"Unsupported file extension: {chosen_ext}")
                
        except Exception as e:
            logger.error(f"Falcon repository Import failed: {str(e)}")
            raise RuntimeError(f"Falcon repository file data loading failed: {e}") from e
        finally:
            self._cleanup_temp_dir()

    async def _parse_json_file(
        self, file_path: str, rel_path_posix: str, encodings: List[str]
    ) -> FileLoadResult:
        """Parse a JSON file (array or single object).
        
        Args:
            file_path: Absolute path to the JSON file
            rel_path_posix: Repository-relative path in POSIX format
            encodings: List of encodings to try
            
        Returns:
            FileLoadResult with parsed data
        """
        rows: List[Row] = []
        failures: List[FailureDetail] = []
        used_encoding: Optional[str] = None
        
        # Try reading with different encodings
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                    
                try:
                    data = json.loads(content)
                    
                    # Handle JSON array
                    if isinstance(data, list):
                        for idx, item in enumerate(data, start=1):
                            rows.append(Row(line_no=idx, data=item))
                    # Handle single JSON object
                    elif isinstance(data, dict):
                        rows.append(Row(line_no=1, data=data))
                    else:
                        # Handle primitive types (string, number, etc.)
                        rows.append(Row(line_no=1, data=data))
                        
                    used_encoding = enc
                    break
                    
                except json.JSONDecodeError as e:
                    failures.append(
                        FailureDetail(
                            line_no=1,
                            error=f"JSON decode error: {str(e)}",
                            line=content[:200],
                        )
                    )
                    used_encoding = enc
                    break
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Read json with encoding {enc} failed: {e}")
                continue
        
        # Fallback: read as bytes and decode with ASCII ignoring errors
        if used_encoding is None:
            try:
                with open(file_path, "rb") as f:
                    content = f.read().decode("ascii", errors="ignore")
                    
                try:
                    data = json.loads(content)
                    
                    if isinstance(data, list):
                        for idx, item in enumerate(data, start=1):
                            rows.append(Row(line_no=idx, data=item))
                    elif isinstance(data, dict):
                        rows.append(Row(line_no=1, data=data))
                    else:
                        rows.append(Row(line_no=1, data=data))
                        
                except json.JSONDecodeError as e:
                    failures.append(
                        FailureDetail(
                            line_no=1,
                            error=f"JSON decode error: {str(e)}",
                            line=content[:200],
                        )
                    )
                    
                used_encoding = "ascii-ignore"
            except Exception as e:
                raise ValueError(f"Failed to read json file: {e}")
        
        return FileLoadResult(
            type="json",
            file_path=rel_path_posix,
            file_name=os.path.basename(file_path),
            encoding=used_encoding,
            rows=rows,
            count=len(rows) + len(failures),
            failed_count=len(failures),
            failures=failures,
        )

    async def _parse_jsonl_file(
        self, file_path: str, rel_path_posix: str, encodings: List[str]
    ) -> FileLoadResult:
        """Parse a JSONL file (line-delimited JSON).
        
        Args:
            file_path: Absolute path to the JSONL file
            rel_path_posix: Repository-relative path in POSIX format
            encodings: List of encodings to try
            
        Returns:
            FileLoadResult with parsed data
        """
        rows: List[Row] = []
        failures: List[FailureDetail] = []
        used_encoding: Optional[str] = None

        # Prefer reading in text mode with multiple encodings
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    for idx, line in enumerate(f, start=1):
                        s = line.strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s)
                            rows.append(Row(line_no=idx, data=obj))
                        except Exception as e:
                            failures.append(
                                FailureDetail(
                                    line_no=idx,
                                    error=str(e),
                                    line=s[:200],
                                )
                            )
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Read jsonl with encoding {enc} failed: {e}")
                continue

        # Fallback: read as bytes and decode with ASCII ignoring errors
        if used_encoding is None:
            try:
                with open(file_path, "rb") as f:
                    for idx, raw_line in enumerate(f, start=1):
                        s = raw_line.decode("ascii", errors="ignore").strip()
                        if not s:
                            continue
                        try:
                            obj = json.loads(s)
                            rows.append(Row(line_no=idx, data=obj))
                        except Exception as e:
                            failures.append(
                                FailureDetail(
                                    line_no=idx,
                                    error=str(e),
                                    line=s[:200],
                                )
                            )
                used_encoding = "ascii-ignore"
            except Exception as e:
                raise ValueError(f"Failed to read jsonl file: {e}")
                
        return FileLoadResult(
            type="jsonl",
            file_path=rel_path_posix,
            file_name=os.path.basename(file_path),
            encoding=used_encoding,
            rows=rows,
            count=(len(rows) + len(failures)),
            failed_count=len(failures),
            failures=failures,
        )

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
        """Download repository with caching, supporting branch URLs"""
        cache_path = self._get_cache_path(repo_url)

        # Use cache if valid
        if os.path.exists(cache_path) and self._is_cache_valid(cache_path):
            logger.info(f"Using cached repository: {cache_path}")
            return self._extract_cache(cache_path)

        # Download fresh copy
        self.temp_dir = tempfile.mkdtemp()

        # Simple parsing for github.com URLs
        github_pattern = r"github\.com/([^/]+)/([^/]+)(?:/tree/(.+))?"
        match = re.search(github_pattern, repo_url)

        if match:
            owner, repo, branch = match.groups()
            branch = branch or "main"  # Default to main if no tree/branch specified
            zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{branch}"
        else:
            # Fallback for generic structure or direct zip links
            if repo_url.endswith(".zip"):
                zip_url = repo_url
            else:
                # Default fallback behavior from original code
                zip_url = (
                        repo_url.replace("github.com", "api.github.com/repos")
                        + "/zipball/main"
                )

        logger.info(f"Downloading from GitHub repo: {zip_url}")

        try:
            if self._http_session is None:
                self._http_session = aiohttp.ClientSession()

            headers = {"Accept": "application/vnd.github.v3+json"}
            async with self._http_session.get(zip_url, headers=headers) as response:
                if response.status != 200:
                    text_resp = await response.text()
                    raise RuntimeError(
                        f"GitHub API Error {response.status}: {text_resp}"
                    )

                zip_path = os.path.join(self.temp_dir, "repo.zip")

                with open(zip_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(1024 * 1024)  # 1MB chunks
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

    def _discover_sqlite_files(self, base_dir: str, search_dir: str) -> List[str]:
        """Find all SQLite files recursively in the search directory"""
        full_search_dir = os.path.join(base_dir, search_dir) if search_dir else base_dir
        if not os.path.exists(full_search_dir):
            raise ValueError(f"Directory not found: {full_search_dir}")

        sqlite_files = []
        for root, _, files in os.walk(full_search_dir):
            for file in files:
                if file.lower().endswith(".sqlite"):
                    full_path = os.path.join(root, file)
                    sqlite_files.append(full_path)
        return sqlite_files

    async def _merge_sqlite_databases(self, sqlite_files: List[str]) -> Dict:
        """Merge multiple SQLite files into the main database"""
        await self.init_connector()
        assert self._connector is not None

        def _worker():
            results = {
                "total_files": len(sqlite_files),
                "successful": 0,
                "failed": 0,
                "tables_merged": [],
            }

            with self._connector.session_scope() as session:
                # 获取底层的 sqlite3 连接对象
                connection_proxy = session.connection()
                # 兼容不同版本的 SQLAlchemy 获取底层连接的方式
                try:
                    # SQLAlchemy 1.4+ / 2.0
                    raw_conn = connection_proxy.connection.dbapi_connection
                except AttributeError:
                    try:
                        # 旧版本或某些驱动
                        raw_conn = connection_proxy.connection
                    except AttributeError:
                        # 最后的尝试
                        raw_conn = session.get_bind().raw_connection()

                # 确保 raw_conn 是 sqlite3 的连接对象
                if not raw_conn:
                    raise RuntimeError("Failed to get raw sqlite3 connection")

                cursor = raw_conn.cursor()

                for db_path in sqlite_files:
                    src_alias = f"src_db_{uuid.uuid4().hex[:8]}"
                    try:
                        try:
                            cursor.execute("PRAGMA database_list")
                            attached_dbs = cursor.fetchall()
                            for _, name, _ in attached_dbs:
                                if name not in ("main", "temp"):
                                    cursor.execute(f"DETACH DATABASE {name}")
                        except Exception as cleanup_err:
                            logger.warning(f"Cleanup warning: {cleanup_err}")

                        cursor.execute(f"ATTACH DATABASE ? AS {src_alias}", (db_path,))

                        cursor.execute(
                            f"SELECT name, sql FROM {src_alias}.sqlite_master "
                            f"WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                        )
                        tables = cursor.fetchall()

                        for table_name, create_sql in tables:
                            cursor.execute(
                                "SELECT name FROM sqlite_master "
                                "WHERE type='table' "
                                "AND name=?",
                                (table_name,),
                            )
                            if not cursor.fetchone():
                                cursor.execute(create_sql)
                                cursor.execute(
                                    f'INSERT INTO main."{table_name}" '
                                    f'SELECT * FROM {src_alias}."{table_name}"'
                                )
                                results["tables_merged"].append(table_name)
                            else:
                                logger.warning(
                                    f"Table '{table_name}' exists. Skipping."
                                )

                        raw_conn.commit()
                        results["successful"] += 1

                    except Exception as e:
                        logger.error(f"Failed to merge {db_path}: {e}")
                        results["failed"] += 1
                        try:
                            raw_conn.rollback()
                        except Exception:
                            pass
                    finally:
                        try:
                            cursor.execute(f"DETACH DATABASE {src_alias}")
                        except Exception:
                            pass

            return results

        return await self._run_in_thread(_worker)

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
