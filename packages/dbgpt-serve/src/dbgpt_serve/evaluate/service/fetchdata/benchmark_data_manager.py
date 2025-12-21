import asyncio
import hashlib
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
    table_mapping_file: Optional[str] = None
    cache_expiry_days: int = 1
    repo_url: str = "https://github.com/eosphoros-ai/Falcon/tree/yifan_1216"
    data_dir: str = "dev_data/dev_databases"


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
            # 使用ThreadPoolExecutor实现超时控制
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
        """Execute query and return results as dict list"""
        await self.init_connector()
        cols, rows = await self._run_in_thread(
            self._query_blocking, query, params, timeout
        )
        return [dict(zip(cols, row)) for row in rows]

    async def load_from_github(
        self, repo_url: str, data_dir: str = "dev_data/dev_databases"
    ) -> Dict:
        """Main method to load data from GitHub repository"""
        try:
            await self.init_connector()

            # 1. Download or use cached repository
            repo_dir = await self._download_repo_contents(repo_url)

            # 2. Find all SQLite files recursively in the specified data_dir
            sqlite_files = self._discover_sqlite_files(repo_dir, data_dir)
            if not sqlite_files:
                raise ValueError(f"No SQLite files found in {data_dir}")
            logger.info(f"Found {len(sqlite_files)} SQLite files")

            # 3. Merge all SQLite files into the main database
            result = await self._merge_sqlite_databases(sqlite_files)
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
