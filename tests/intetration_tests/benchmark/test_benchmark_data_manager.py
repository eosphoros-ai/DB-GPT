import threading
from typing import Optional, Any, Dict, cast, Tuple, List
from sqlalchemy import text
import pytest
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import BenchmarkDataManager


class QueryTimeoutError(Exception):
    """查询超时异常"""
    pass


def test_get_usable_table_names():
    """测试数据库查询功能"""
    conn = SQLiteConnector.from_file_path(
        "/Users/alanchen/ant/project/DB-GPT/pilot/benchmark_meta_data/ant_icube_dev.db")

    try:
        # 测试超时功能
        result = _query_blocking_v2(conn, "WITH daily_stats AS ( SELECT company, date, CAST(high AS real) AS high_price, CAST(low AS real) AS low_price , CAST(high AS real) - CAST(low AS real) AS price_range FROM di_massive_yahoo_finance_dataset_0805 ),  moving_avg AS ( SELECT d1.company, d1.date, d1.price_range, avg(CAST(d2.close AS real)) AS avg_30d_close FROM daily_stats d1 JOIN di_massive_yahoo_finance_dataset_0805 d2 ON d1.company = d2.company AND date(d2.date) BETWEEN date(d1.date, '-30 days') AND date(d1.date) GROUP BY d1.company, d1.date, d1.price_range ) SELECT company AS `company`, date AS `date`, price_range AS `price_range`, avg_30d_close AS `avg_30d_close` FROM moving_avg WHERE price_range > avg_30d_close * 0.5 ORDER BY company, date;", timeout=60.0)
        # result = _query_blocking_v2(conn, "select count(*) from di_massive_yahoo_finance_dataset_0805", timeout=30)
        print("查询完成，结果: ", result)
    except QueryTimeoutError as e:
        print(f"查询超时: {str(e)}")
    except Exception as e:
        print(f"查询出错: {str(e)}")


def _query_blocking(
        _connector, sql: str, params: Optional[Any] = None, timeout: Optional[float] = None
):
    """
    执行数据库查询，支持超时控制

    Args:
        _connector: 数据库连接器
        sql: SQL查询语句
        params: 查询参数
        timeout: 超时时间（秒），None表示不设置超时

    Returns:
        tuple: (列名列表, 行数据列表)

    Raises:
        QueryTimeoutError: 查询超时
        Exception: 其他查询错误
    """
    assert _connector is not None, "Connector not initialized"

    if timeout is None:
        return _execute_query(_connector, sql, params)

    # 使用线程和事件实现超时控制
    result = {'data': None, 'error': None}
    done_event = threading.Event()
    cancel_event = threading.Event()

    def execute_query():
        try:
            result['data'] = _execute_query(_connector, sql, params, cancel_event)
        except Exception as e:
            result['error'] = e
        finally:
            done_event.set()

    # 启动查询线程（daemon=True确保程序可以正常退出）
    thread = threading.Thread(target=execute_query, daemon=True)
    thread.start()

    # 等待查询完成或超时
    if done_event.wait(timeout=timeout):
        if result['error']:
            raise result['error']
        return result['data']
    else:
        # 触发取消标记，要求后台线程尽快中断
        cancel_event.set()
        # 尽力等待子线程尽快退出，避免成为“僵尸线程”
        thread.join(timeout=2.0)
        raise QueryTimeoutError(f"查询超时，超过了 {timeout} 秒")


def _execute_query(_connector, sql: str, params: Optional[Any] = None, cancel_event: Optional[threading.Event] = None):
    """执行数据库查询（支持取消）"""
    with _connector.session_scope() as session:
        # 针对 SQLite，通过底层 DB-API 连接的 progress handler 支持查询取消
        dbapi_conn = None
        progress_installed = False
        try:
            if getattr(_connector, "dialect", None) == "sqlite" and cancel_event is not None:
                try:
                    # 取出底层 DB-API 连接对象（pysqlite 的 sqlite3.Connection）
                    conn = session.connection()
                    dbapi_conn = getattr(conn, "connection", None)
                    if dbapi_conn is not None and hasattr(dbapi_conn, "set_progress_handler"):
                        def _progress_handler():
                            # 返回非零将中断当前语句执行
                            return 1 if cancel_event.is_set() else 0
                        # 每执行一定步数回调一次，数值越小开销越大；此处取一个折中值
                        dbapi_conn.set_progress_handler(_progress_handler, 10000)
                        progress_installed = True
                except Exception:
                    # 安装进度处理器失败则忽略，回退为不可中断
                    progress_installed = False

            cursor = session.execute(text(sql), params or {})

            if cursor.returns_rows:
                return list(cursor.keys()), cursor.fetchall()
            else:
                return [], []
        finally:
            # 清理 progress handler，避免影响连接的后续使用
            if progress_installed and dbapi_conn is not None:
                try:
                    dbapi_conn.set_progress_handler(None, 0)
                except Exception:
                    pass


def _query_blocking_v2(
    _connector, sql: str, params: Optional[Any] = None, timeout: Optional[float] = None
):

    # 结果容器与同步事件
    result: Dict[str, Any] = {"data": None, "error": None}
    done_event = threading.Event()
    cancel_event = threading.Event()

    def _execute_query():
        dbapi_conn = None
        progress_installed = False
        try:
            with _connector.session_scope() as session:
                # SQLite 下安装 progress handler，以便在取消时中断执行
                try:
                    if getattr(_connector, "dialect", None) == "sqlite":
                        conn = session.connection()
                        dbapi_conn = getattr(conn, "connection", None)
                        if dbapi_conn is not None and hasattr(dbapi_conn, "set_progress_handler"):
                            def _progress_handler():
                                # 置位取消后返回非零，中断当前语句
                                return 1 if cancel_event.is_set() else 0
                            dbapi_conn.set_progress_handler(_progress_handler, 10000)
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
