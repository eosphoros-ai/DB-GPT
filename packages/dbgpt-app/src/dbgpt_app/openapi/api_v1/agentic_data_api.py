import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from collections import OrderedDict
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import RLock
from typing import TYPE_CHECKING, Any, AsyncGenerator, Callable, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt._private.pydantic import BaseModel as _BaseModel
from dbgpt.agent.core.context import ContextBudgetConfig
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.skill.manage import get_skill_manager
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import SKILLS_DIR, resolve_root_path
from dbgpt.core import PromptTemplate
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt_app.openapi.api_v1.report_data_guard import (
    SqlResult,
    validate_html_report_data,
)
from dbgpt_app.openapi.api_view_model import (
    ConversationVo,
    Result,
)
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from dbgpt.agent.core.memory.gpts import GptsMemory


class _ReactAgentMemoryCacheEntry:
    def __init__(self, memory: "GptsMemory", updated_at: float):
        self.memory = memory
        self.updated_at = updated_at


class _ReactAgentMemoryCache:
    def __init__(self, max_entries: int, ttl_seconds: int):
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._entries: "OrderedDict[str, _ReactAgentMemoryCacheEntry]" = OrderedDict()
        self._active_counts: Dict[str, int] = {}
        self._lock = RLock()

    def acquire(self, conv_id: str) -> None:
        with self._lock:
            self._active_counts[conv_id] = self._active_counts.get(conv_id, 0) + 1
            self._touch_locked(conv_id)

    def release(self, conv_id: str) -> None:
        with self._lock:
            active_count = self._active_counts.get(conv_id, 0)
            if active_count <= 1:
                self._active_counts.pop(conv_id, None)
            else:
                self._active_counts[conv_id] = active_count - 1
            self._evict_locked(time.monotonic())

    def get_or_create(self, conv_id: str, factory: Callable[[], "GptsMemory"]):
        now = time.monotonic()
        with self._lock:
            self._evict_locked(now)
            entry = self._entries.get(conv_id)
            if entry is not None:
                entry.updated_at = now
                self._entries.move_to_end(conv_id)
                return entry.memory

            memory = factory()
            self._entries[conv_id] = _ReactAgentMemoryCacheEntry(memory, now)
            self._evict_locked(now)
            return memory

    def _touch_locked(self, conv_id: str) -> None:
        entry = self._entries.get(conv_id)
        if entry is not None:
            entry.updated_at = time.monotonic()
            self._entries.move_to_end(conv_id)

    def _evict_locked(self, now: float) -> None:
        for conv_id, entry in list(self._entries.items()):
            if self._is_active_locked(conv_id):
                continue
            if now - entry.updated_at >= self._ttl_seconds:
                self._discard_locked(conv_id)

        while len(self._entries) > self._max_entries:
            evicted = False
            for conv_id in list(self._entries.keys()):
                if self._is_active_locked(conv_id):
                    continue
                self._discard_locked(conv_id)
                evicted = True
                break
            if not evicted:
                break

    def _discard_locked(self, conv_id: str) -> None:
        entry = self._entries.pop(conv_id, None)
        if entry is None:
            return
        try:
            entry.memory.clear(conv_id)
        except Exception:
            logger.debug(
                "Failed to clear ReAct agent memory for %s", conv_id, exc_info=True
            )
        executor = getattr(entry.memory, "_executor", None)
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)

    def _is_active_locked(self, conv_id: str) -> bool:
        return self._active_counts.get(conv_id, 0) > 0


REACT_AGENT_MEMORY_CACHE = _ReactAgentMemoryCache(
    max_entries=int(os.getenv("DBGPT_REACT_AGENT_MEMORY_CACHE_MAX_ENTRIES", "1000")),
    ttl_seconds=int(os.getenv("DBGPT_REACT_AGENT_MEMORY_CACHE_TTL_SECONDS", "3600")),
)

DEFAULT_SKILLS_DIR = SKILLS_DIR
AUTO_DATA_MARKER_PATTERN = re.compile(
    r"###([A-Z0-9_]+)_START###\s*(.*?)\s*###\1_END###", re.DOTALL
)


def _skill_metadata_name(skill: Any) -> str:
    metadata = getattr(skill, "metadata", None)
    return str(
        getattr(metadata, "name", None)
        or getattr(skill, "name", None)
        or ""
    )


def _skill_file_path(skill: Any, skills_dir: str) -> str:
    metadata = getattr(skill, "metadata", None)
    file_path = str(getattr(metadata, "file_path", None) or "")
    if not file_path and hasattr(skill, "_config"):
        file_path = str(skill._config.get("file_path", "") or "")
    if not file_path:
        return ""

    try:
        return str(
            Path(file_path)
            .expanduser()
            .resolve()
            .relative_to(Path(skills_dir).expanduser().resolve())
        )
    except Exception:
        return file_path


def _resolve_skill_file_path(
    skill_name: str,
    file_path: str,
    all_skills: List[Any],
    skills_dir: str,
) -> str:
    """Resolve a skill path when the model calls load_skill without file_path."""
    if file_path:
        return file_path

    normalized_name = (skill_name or "").strip().lower()
    if not normalized_name:
        return ""

    for skill in all_skills:
        if _skill_metadata_name(skill).strip().lower() == normalized_name:
            return _skill_file_path(skill, skills_dir)

    for skill in all_skills:
        candidate = _skill_file_path(skill, skills_dir)
        if not candidate:
            continue
        path = Path(candidate)
        aliases = {
            path.stem.lower(),
            path.parent.name.lower(),
            candidate.strip().lower(),
        }
        if normalized_name in aliases:
            return candidate

    return ""


def _validate_upload_filename(filename: str) -> str:
    if "\x00" in filename:
        raise ValueError("filename must not contain null bytes")

    posix_path = PurePosixPath(filename)
    windows_path = PureWindowsPath(filename)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or len(posix_path.parts) != 1
        or len(windows_path.parts) != 1
        or filename in {"", ".", ".."}
    ):
        raise ValueError("filename must be a plain file name")
    return filename


async def _resolve_model_context_tokens(
    llm_client: Any, model_name: Optional[str]
) -> Optional[int]:
    """Resolve model context window from runtime model metadata."""
    if not llm_client or not model_name:
        return None

    try:
        metadata = await llm_client.get_model_metadata(model_name)
        context_length = getattr(metadata, "context_length", None)
        if isinstance(context_length, int) and context_length > 0:
            return context_length
    except Exception:
        logger.debug(
            "Failed to resolve context window for model %s", model_name, exc_info=True
        )
    return None


def _postgres_sql_dialect_rules(
    database_name: Optional[str] = None,
    ads_only_operation: bool = False,
    dim_only_basic_resource: bool = False,
) -> str:
    """Return PostgreSQL-only SQL rules for the React data assistant prompt."""
    rules = """
## PostgreSQL SQL 方言规则
- 当前数据库固定为 PostgreSQL，只能生成 PostgreSQL 语法。
- 禁止使用 MySQL/SQLite/SQL Server 语法。
- 禁止使用反引号 `identifier`，表名和字段名默认不要加引号；确需引用标识符时使用双引号。
- 字符串和日期常量必须使用单引号，例如 '2026-05-01'。
- 日期运算使用 PostgreSQL 写法：CURRENT_DATE - INTERVAL '7 days'。
- 日期格式化使用 TO_CHAR(date_col, 'YYYY-MM-DD')。
- 空值处理使用 COALESCE(col, 0)，不要使用 IFNULL 或 NVL。
- 条件聚合优先使用 SUM(CASE WHEN ... THEN ... ELSE ... END)。
- 字符串聚合使用 STRING_AGG(col::text, ',')，不要使用 GROUP_CONCAT。
- 分页使用 LIMIT n OFFSET m，不要使用 LIMIT m,n。
- 类型转换使用 CAST(col AS type) 或 col::type。
- 查询前必须只使用“表结构”里真实存在的表名和字段名。
- 所有 SQL 必须是单条 SELECT / WITH ... SELECT，禁止多语句。
- PostgreSQL 中 ROUND(double precision, integer) 会报错；比例、均值、
  里程等小数保留必须写成 ROUND((expr)::numeric, n)。
- UNION/UNION ALL 每个 SELECT 对应列类型必须一致，日期和文本混用时先统一
  CAST(... AS text) 或统一保持 date 类型。
"""
    if (database_name or "").lower() == "bus_info":
        rules += """
## bus_info 隐私与安全字段规则
- 手机号、身份证号、证件号、联系方式、电话、邮箱、住址、家庭地址等隐私或安全字段
  不得明文输出给用户。
- 查询这些字段时必须在 SQL 中脱敏展示，例如直接输出 '***'，或仅保留必要尾号：
  `CONCAT('***', RIGHT(phone, 4)) AS phone`。
- 最终回答和 HTML 报表也只能展示脱敏后的值；如果本轮 SQL 已返回明文敏感值，
  回答时必须改写为 `***`，不得复述原文。
"""

    if (database_name or "").lower() == "bus_info" and dim_only_basic_resource:
        rules += """
## bus_info 公司基础资源 DIM 表约束
- 当前问题已识别为公司基础资源类问题，优先且仅使用 dim_ 开头的维表。
- 适用范围包括公司/部门/车队/线路/车辆/驾驶员等基础档案、清单、列表、资源信息。
- 不要使用 ads_ 运营汇总表回答基础资源清单问题；ads_ 用于运营指标统计，不用于基础档案。
- 如果 dim_ 表缺少所需字段，必须明确说明当前维表不支持该字段，不要回退到 dwd_、
  ods_、ads_、bigdata_ 等表。
"""
    elif (database_name or "").lower() == "bus_info" and ads_only_operation:
        rules += """
## bus_info 运营类 ADS 表约束
- 当前问题已识别为运营类问题，只能使用 ads_ 开头的 ADS 汇总表。
- 不要回退查询 dwd_、dim_、ods_、bigdata_ 等明细表或维表。
- 如果 ADS 表缺少所需字段或粒度，必须明确说明当前汇总表不支持该指标，
  不要臆造字段、不要使用未提供的表。
- ads_ope_ontime_assess_d 不存在 zd_cnt；准点统计使用 start_cnt、start_zd_cnt、
  back_cnt、back_zd_cnt 等表结构中真实字段。
- ads_ope_summary_line_d 不存在 driver_number；驾驶员维度使用
  ads_ope_summary_driver_d 或表结构中明确包含驾驶员字段的 ADS 表。
"""
    elif (database_name or "").lower() == "bus_info":
        rules += """
## bus_info 已验证业务字段规则
- 运营类数据查询（运营/营运/班次/线路/驾驶员/车辆/客流/收入/里程/
  准点/计划/趟次/日报/明细/统计/报表等）必须选用 ads_ 开头的 ADS 汇总表；
  不要回退使用 dwd_、dim_、bigdata_ 等明细表或维表。
- bigdata_ticket_revenue 使用 revenue_date 作为日期字段，不要使用 target_date。
- dim_resource_line 不存在 delete_flag，过滤线路时不要自动追加 delete_flag 条件。
- ads_ope_ontime_assess_d 不存在 zd_cnt；准点统计使用 start_cnt、start_zd_cnt、
  back_cnt、back_zd_cnt 等表结构中真实字段。
- ads_ope_summary_line_d 不存在 driver_number；驾驶员维度使用
  ads_ope_summary_driver_d 或表结构中明确包含驾驶员字段的表。
- dim_fleet_vehicle 车辆编号优先使用 inner_code，车牌使用 license_plate；
  不要臆造 vehicle_code。
"""
    return rules.strip()


_BUS_OPERATION_KEYWORDS = (
    "运营",
    "营运",
    "班次",
    "线路",
    "驾驶员",
    "司机",
    "车辆",
    "客流",
    "收入",
    "票款",
    "里程",
    "准点",
    "计划",
    "趟次",
    "日报",
    "日运营",
    "运营日报",
    "明细",
    "统计",
    "报表",
)


_BUS_BASIC_RESOURCE_KEYWORDS = (
    "基础资源",
    "基础信息",
    "资源清单",
    "资源列表",
    "基础档案",
    "档案",
    "清单",
    "列表",
    "名录",
    "公司资源",
    "车辆资源",
    "车辆档案",
    "驾驶员档案",
    "司机档案",
    "线路清单",
    "部门清单",
    "车队清单",
)


_BUS_SCHEMA_INSPECTION_KEYWORDS = (
    "表字段",
    "字段名",
    "字段列表",
    "字段清单",
    "字段说明",
    "表结构",
    "建表",
    "schema",
    "ddl",
)


_BUS_RAW_PERSONNEL_KEYWORDS = (
    "人员表",
    "员工表",
    "人员数据",
    "员工数据",
    "人员明细",
    "员工明细",
    "人员信息",
    "员工信息",
    "dim_hr_employee",
)


_RAW_DETAIL_ACTION_KEYWORDS = (
    "返回",
    "查看",
    "看看",
    "前",
    "全部",
    "明细",
    "原始",
    "列表",
    "清单",
)


def _is_bus_schema_inspection_question(
    database_name: Optional[str],
    user_question: Optional[str],
) -> bool:
    """Return whether a bus_info question asks to expose schema details."""
    if (database_name or "").lower() != "bus_info":
        return False
    question = (user_question or "").lower()
    return any(
        keyword.lower() in question
        for keyword in _BUS_SCHEMA_INSPECTION_KEYWORDS
    )


def _is_bus_raw_personnel_detail_question(
    database_name: Optional[str],
    user_question: Optional[str],
) -> bool:
    """Return whether a bus_info question asks for raw personnel detail rows."""
    if (database_name or "").lower() != "bus_info":
        return False
    question = (user_question or "").lower()
    has_personnel = any(
        keyword.lower() in question for keyword in _BUS_RAW_PERSONNEL_KEYWORDS
    )
    has_raw_action = any(
        keyword.lower() in question for keyword in _RAW_DETAIL_ACTION_KEYWORDS
    )
    return has_personnel and has_raw_action


def _is_bus_basic_resource_question(
    database_name: Optional[str],
    user_question: Optional[str],
) -> bool:
    """Return whether a bus_info question should prefer DIM resource tables."""
    if (database_name or "").lower() != "bus_info":
        return False
    question = (user_question or "").lower()
    return any(keyword.lower() in question for keyword in _BUS_BASIC_RESOURCE_KEYWORDS)


def _is_bus_operation_question(
    database_name: Optional[str],
    user_question: Optional[str],
) -> bool:
    """Return whether the user question should be constrained to bus ADS tables."""
    if (database_name or "").lower() != "bus_info":
        return False
    question = (user_question or "").lower()
    return any(keyword.lower() in question for keyword in _BUS_OPERATION_KEYWORDS)


def _normalize_table_name(table_name: str) -> str:
    """Normalize schema-qualified or quoted table names to bare lower-case names."""
    bare_name = table_name.strip().strip('"`')
    if "." in bare_name:
        bare_name = bare_name.rsplit(".", 1)[-1]
    return bare_name.strip('"`').lower()


def _filter_table_info_by_names(table_info: str, allowed_names: List[str]) -> str:
    """Keep only CREATE TABLE blocks for the provided table names."""
    allowed = {_normalize_table_name(name) for name in allowed_names}
    if not table_info or not allowed:
        return table_info

    blocks = re.split(r"(?=CREATE\s+TABLE\s+)", table_info, flags=re.IGNORECASE)
    kept: List[str] = []
    for block in blocks:
        match = re.search(
            r"CREATE\s+TABLE\s+(?:(?:[A-Za-z_][\w$]*)\.)?[\"`]?([A-Za-z_][\w$]*)[\"`]?",
            block,
            flags=re.IGNORECASE,
        )
        if match and _normalize_table_name(match.group(1)) in allowed:
            kept.append(block.strip())

    return "\n\n".join(kept) if kept else table_info


_SCHEMA_LEAK_SAFE_MESSAGE = (
    "已根据可用业务数据完成处理。出于安全要求，底层数据字典和数据库实现细节不展示给客户。"
)


def _get_direct_customer_facing_reply(
    database_name: Optional[str],
    user_question: Optional[str],
) -> Optional[str]:
    """Return a direct customer-facing answer for requests that must not run tools."""
    if _is_bus_schema_inspection_question(database_name, user_question):
        return _SCHEMA_LEAK_SAFE_MESSAGE
    return None


_SENSITIVE_COLUMN_KEYWORDS = (
    "mobile",
    "phone",
    "tel",
    "id_num",
    "id_card",
    "identity",
    "cert",
    "urgent",
    "email",
    "address",
    "addr",
    "ic_no",
    "physical_no",
)


def _is_sensitive_column_name(column_name: Any) -> bool:
    """Return whether a SQL column should be masked before display."""
    normalized = str(column_name or "").strip().lower()
    return any(keyword in normalized for keyword in _SENSITIVE_COLUMN_KEYWORDS)


def _mask_sensitive_value(value: Any) -> Any:
    """Mask a sensitive SQL value while preserving empty/null values."""
    if value in (None, ""):
        return value
    return "***"


def _mask_sensitive_sql_rows(col_names: List[str], rows: List[Any]) -> List[List[Any]]:
    """Mask sensitive SQL result columns before display and memory storage."""
    sensitive_indexes = {
        idx
        for idx, col_name in enumerate(col_names)
        if _is_sensitive_column_name(col_name)
    }
    masked_rows: List[List[Any]] = []
    for row in rows:
        row_values = list(row)
        masked_rows.append(
            [
                _mask_sensitive_value(value) if idx in sensitive_indexes else value
                for idx, value in enumerate(row_values)
            ]
        )
    return masked_rows


def _mask_labeled_sensitive_text(text: str) -> str:
    """Mask labeled sensitive values in customer-facing free text."""
    label_pattern = (
        r"((?:手机号|手机|电话|联系方式|身份证号|身份证|证件号|邮箱|住址|地址|"
        r"mobile_phone|phone|tel|id_num|id_card|email|address)"
        r"\s*[:：]\s*)"
        r"([^，,。\n\r|]+)"
    )
    return re.sub(
        label_pattern,
        lambda match: match.group(1) + "***",
        text,
        flags=re.IGNORECASE,
    )


def _text_contains_schema_details(text: str) -> bool:
    """Return whether customer-facing text appears to expose DB schema details."""
    if not isinstance(text, str) or not text.strip():
        return False
    schema_patterns = [
        r"\bCREATE\s+TABLE\b",
        r"\bALTER\s+TABLE\b",
        r"\bDROP\s+TABLE\b",
        r"\b(?:dim|ads|dwd|ods|bigdata)_[A-Za-z0-9_]+\b.*字段",
        r"字段.*\b(?:dim|ads|dwd|ods|bigdata)_[A-Za-z0-9_]+\b",
        r"表共有\s*\d+\s*个?字段",
        r"字段名",
        r"\b\d+\.\s*[A-Za-z_][\w$]*\s*[:：]\s*字段",
        r"可用表\s*[:：]",
        r"表结构\s*[:：]",
        r"字段清单\s*[:：]",
        r"字段列表\s*[:：]",
    ]
    return any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in schema_patterns
    )


def _sanitize_customer_facing_answer(value: Any) -> Any:
    """Remove schema details from final customer-facing answers."""
    if isinstance(value, dict):
        return {
            key: _sanitize_customer_facing_answer(item)
            if key in {"content", "result", "text", "markdown"}
            or isinstance(item, (dict, list))
            else item
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_customer_facing_answer(item) for item in value]
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if stripped[:1] in ("{", "["):
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if parsed is not None:
            return json.dumps(
                _sanitize_customer_facing_answer(parsed),
                ensure_ascii=False,
            )

    if _text_contains_schema_details(value):
        return _SCHEMA_LEAK_SAFE_MESSAGE
    return _mask_labeled_sensitive_text(value)


def _sanitize_customer_facing_action_input(action: Any, action_input: Any) -> Any:
    """Sanitize customer-facing action payloads without hiding SQL components."""
    if str(action or "").strip().lower() == "sql_query" and action_input:
        return _mask_labeled_sensitive_text(action_input)
    return _sanitize_customer_facing_answer(action_input)


def _sanitize_customer_facing_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """Remove schema and sensitive details from a customer-visible step."""
    sanitized = dict(step)
    action = sanitized.get("action")
    for key in ("thought", "action_intention", "action_reason"):
        sanitized[key] = _sanitize_customer_facing_answer(sanitized.get(key))
    sanitized["action_input"] = _sanitize_customer_facing_action_input(
        action,
        sanitized.get("action_input"),
    )
    outputs = []
    for item in sanitized.get("outputs") or []:
        if isinstance(item, dict):
            cleaned_item = dict(item)
            cleaned_item["content"] = _sanitize_customer_facing_answer(
                cleaned_item.get("content")
            )
            outputs.append(cleaned_item)
        else:
            outputs.append(_sanitize_customer_facing_answer(item))
    sanitized["outputs"] = outputs
    return sanitized


def _build_database_context(
    database_name: str,
    user_question: Optional[str],
    table_names: List[str],
    table_info: str,
) -> str:
    """Build database prompt context, narrowing bus questions to intent tables."""
    dim_only_basic_resource = _is_bus_basic_resource_question(
        database_name,
        user_question,
    )
    ads_only_operation = (
        not dim_only_basic_resource
        and _is_bus_operation_question(database_name, user_question)
    )
    visible_table_names = table_names
    visible_table_info = table_info
    if dim_only_basic_resource:
        visible_table_names = [
            table_name
            for table_name in table_names
            if _normalize_table_name(table_name).startswith("dim_")
        ]
        visible_table_info = _filter_table_info_by_names(
            table_info, visible_table_names
        )
    elif ads_only_operation:
        visible_table_names = [
            table_name
            for table_name in table_names
            if _normalize_table_name(table_name).startswith("ads_")
        ]
        visible_table_info = _filter_table_info_by_names(
            table_info, visible_table_names
        )

    postgres_sql_rules = _postgres_sql_dialect_rules(
        database_name,
        ads_only_operation=ads_only_operation,
        dim_only_basic_resource=dim_only_basic_resource,
    )
    operation_hint = ""
    if dim_only_basic_resource:
        operation_hint = (
            "\n- 当前问题已识别为公司基础资源类问题，本轮只提供 dim_ 开头的维表。"
        )
    elif ads_only_operation:
        operation_hint = (
            "\n- 当前问题已识别为运营类问题，本轮只提供 ads_ 开头的 ADS 汇总表。"
        )
    return f"""
## 数据库信息
- 数据库名: {database_name}
- 可用表: {", ".join(visible_table_names)}
- 表结构:
{visible_table_info}
- 使用 'sql_query' 工具执行 SQL 查询
- **只允许 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE**{operation_hint}
- **表结构仅供内部生成 SQL 使用，不得向客户展示表结构、字段清单、
  CREATE TABLE、底层 SQL 或数据库实现细节。**
{postgres_sql_rules}
"""


def _strip_sql_literals_and_comments(sql: str) -> str:
    """Remove SQL comments and string literals before lightweight table parsing."""
    sql = re.sub(r"--[^\n\r]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"'(?:''|[^'])*'", "''", sql)
    return sql


def _extract_referenced_sql_tables(sql: str) -> List[str]:
    """Extract table names referenced by FROM/JOIN in a SELECT/WITH query."""
    cleaned_sql = _strip_sql_literals_and_comments(sql)
    cte_names = {
        _normalize_table_name(match.group(1))
        for match in re.finditer(
            r"(?:\bWITH\b|,)\s+([A-Za-z_][\w$]*)\s+AS\s*\(",
            cleaned_sql,
            flags=re.IGNORECASE,
        )
    }
    referenced: List[str] = []
    for match in re.finditer(
        r"\b(?:FROM|JOIN)\s+"
        r"((?:(?:[\"`]?[A-Za-z_][\w$]*[\"`]?)\.)?"
        r"[\"`]?[A-Za-z_][\w$]*[\"`]?)",
        cleaned_sql,
        flags=re.IGNORECASE,
    ):
        table_name = _normalize_table_name(match.group(1))
        if table_name and table_name not in cte_names:
            referenced.append(table_name)
    return referenced


def _validate_bus_operation_sql_tables(
    database_name: Optional[str],
    user_question: Optional[str],
    sql: str,
) -> Optional[str]:
    """Reject non-ADS table references for bus operation questions."""
    if not _is_bus_operation_question(database_name, user_question):
        return None

    referenced_tables = _extract_referenced_sql_tables(sql)
    disallowed_tables = sorted(
        {table for table in referenced_tables if not table.startswith("ads_")}
    )
    if not disallowed_tables:
        return None

    return (
        "运营类问题只能查询 ads_ 开头的汇总表。当前 SQL 引用了非 ADS 表: "
        f"{', '.join(disallowed_tables)}。请改用表结构中提供的 ads_ 表；"
        "如果 ADS 表不支持该指标，请直接说明无法从当前汇总表获得，"
        "不能回退到明细表或维表。"
    )


def _validate_bus_table_policy_sql(
    database_name: Optional[str],
    user_question: Optional[str],
    sql: str,
) -> Optional[str]:
    """Reject table families that do not match the bus_info question intent."""
    if _is_bus_schema_inspection_question(database_name, user_question):
        return (
            "底层数据字典和数据库实现细节不展示给客户。请改为按业务问题查询数据，"
            "不要返回底层清单、建表语句或结构说明。"
        )

    if _is_bus_basic_resource_question(database_name, user_question):
        referenced_tables = _extract_referenced_sql_tables(sql)
        disallowed_tables = sorted(
            {table for table in referenced_tables if not table.startswith("dim_")}
        )
        if disallowed_tables:
            return (
                "基础资源类问题只能查询 dim_ 开头的维表。当前 SQL 引用了非 DIM 表: "
                f"{', '.join(disallowed_tables)}。请改用表结构中提供的 dim_ 表；"
                "如果 DIM 表不支持该字段，请直接说明无法从当前维表获得。"
            )
        return None

    return _validate_bus_operation_sql_tables(database_name, user_question, sql)


def _serialize_sql_results_for_code(
    sql_results: List[SqlResult],
) -> List[Dict[str, Any]]:
    """Serialize saved SQL results for code_interpreter access."""
    serialized: List[Dict[str, Any]] = []
    for idx, result in enumerate(sql_results, start=1):
        serialized.append(
            {
                "ref": f"SQL_RESULT_{idx}",
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
                "sql": result.sql,
            }
        )
    return serialized


_SQL_DISPLAY_COLUMN_LABELS = {
    "id": "编号",
    "name": "姓名",
    "sex": "性别",
    "mobile_phone": "手机号",
    "phone": "电话",
    "urgent_phone": "紧急联系电话",
    "id_num": "身份证号",
    "id_card": "身份证号",
    "email": "邮箱",
    "address": "地址",
    "home_address": "住址",
    "pos_name": "职位",
    "employee_num": "员工编号",
    "department_name": "部门名称",
    "company_name": "公司名称",
    "line_name": "线路名称",
}


def _customer_facing_sql_column_label(col_name: str) -> str:
    """Map internal SQL result column names to customer-facing labels."""
    normalized = str(col_name or "").strip().lower()
    if normalized in _SQL_DISPLAY_COLUMN_LABELS:
        return _SQL_DISPLAY_COLUMN_LABELS[normalized]
    if _is_sensitive_column_name(normalized):
        return "敏感信息"
    return str(col_name)


def _code_uses_saved_sql_results(
    code: str,
    sql_results: List[SqlResult] | List[Dict[str, Any]],
) -> bool:
    """Return whether code is backed by this round's saved SQL results."""
    if not sql_results:
        return False
    return _code_selects_saved_sql_results(code) or any(
        marker in code
        for marker in [
            "save_report_facts(",
            "load_report_facts(",
        ]
    )


def _code_selects_saved_sql_results(code: str) -> bool:
    """Return whether code directly selects this round's saved SQL results."""
    sql_result_markers = [
        "SQL_QUERY_RESULTS",
        "SQL_RESULTS_PATH",
        "get_sql_result(",
        "get_only_sql_result(",
        "find_sql_result_by_columns(",
        "sql_result_rows(",
    ]
    return any(marker in code for marker in sql_result_markers)


def _report_facts_sidecar_path(html_path: str) -> str:
    """Return the sidecar path that stores facts used by a SQL HTML report."""
    return f"{html_path}.facts.json"


def _has_report_facts_sidecar(html_path: str) -> bool:
    """Return whether a SQL HTML report has a readable facts sidecar."""
    facts_path = _report_facts_sidecar_path(html_path)
    try:
        with open(facts_path, "r", encoding="utf-8") as facts_file:
            facts = json.load(facts_file)
    except Exception:
        return False
    return isinstance(facts, dict)


def _code_writes_html_report(code: str) -> bool:
    """Return whether code appears to write an HTML report file."""
    if not re.search(r"""["'][^"'\n\r]+?\.html?["']""", code, re.IGNORECASE):
        return False
    return bool(
        re.search(r"\bopen\s*\(", code)
        or re.search(r"\.write_text\s*\(", code)
        or re.search(r"\.write_bytes\s*\(", code)
    )


def _available_sql_result_refs(
    sql_results: List[SqlResult] | List[Dict[str, Any]],
) -> List[str]:
    """Return SQL_RESULT refs available to code_interpreter."""
    refs: List[str] = []
    for idx, result in enumerate(sql_results, start=1):
        ref = ""
        if isinstance(result, dict):
            ref = str(result.get("ref") or "")
        refs.append(ref or f"SQL_RESULT_{idx}")
    return refs


def _invalid_sql_result_ref_error(
    code: str,
    sql_results: List[SqlResult] | List[Dict[str, Any]],
) -> Optional[str]:
    """Return an error if code references unavailable SQL_RESULT refs."""
    available_refs = _available_sql_result_refs(sql_results)
    available_ref_set = set(available_refs)
    literal_refs = re.findall(
        r"\bget_sql_result\s*\(\s*['\"](SQL_RESULT_\d+)['\"]\s*\)",
        code,
    )
    missing_refs = sorted({ref for ref in literal_refs if ref not in available_ref_set})
    if missing_refs:
        return (
            "SQL 报告代码引用了不存在的 SQL 结果: "
            f"{', '.join(missing_refs)}。当前可用结果为: "
            f"{', '.join(available_refs)}。请使用真实存在的 "
            "get_sql_result('SQL_RESULT_n')，或用 "
            "find_sql_result_by_columns([...]) 按字段定位。"
        )

    dynamic_calls = re.findall(
        r"\bget_sql_result\s*\(\s*([^'\"\s][^)]*)\)",
        code,
    )
    if dynamic_calls:
        return (
            "SQL 报告代码不能使用变量动态选择 get_sql_result(ref)。请显式使用 "
            "get_sql_result('SQL_RESULT_n') 选择当前可用结果，或用 "
            "find_sql_result_by_columns([...]) 按字段定位。"
        )
    return None


def _invalid_helper_import_error(code: str) -> Optional[str]:
    """Return an error if code imports helper modules that do not exist."""
    blocked_modules = ["utils", "tool_functions"]
    blocked_pattern = (
        r"^\s*(?:from\s+({modules})(?:\.[A-Za-z_][\w.]*)?\s+import\b|"
        r"import\s+({modules})(?:\s|$))"
    ).format(modules="|".join(re.escape(module) for module in blocked_modules))
    matches = re.findall(blocked_pattern, code, flags=re.MULTILINE)
    modules = sorted({module for match in matches for module in match if module})
    if not modules:
        return None
    return (
        "SQL 报告代码不能 import 不存在的 helper 模块: "
        f"{', '.join(modules)}。SQL helper 已自动注入当前执行环境，"
        "请直接调用 get_sql_result、find_sql_result_by_columns、"
        "require_columns、require_value、to_float、write_sql_report_html 等函数。"
    )


def _unknown_sql_result_helpers(code: str) -> List[str]:
    """Return SQL-result helper names that are not provided at runtime."""
    allowed_helpers = {
        "get_sql_result",
        "get_only_sql_result",
        "find_sql_result_by_columns",
        "sql_result_rows",
        "require_columns",
        "require_value",
        "to_float",
        "save_report_facts",
        "load_report_facts",
        "write_sql_report_html",
    }
    helper_names = set(
        re.findall(
            r"\b(?:get_sql_result|find_sql_result_by_[A-Za-z0-9_]+|"
            r"get_only_sql_result|sql_result_rows|require_columns|require_value|"
            r"to_[A-Za-z0-9_]+|save_report_facts|load_report_facts|"
            r"write_sql_report_html)"
            r"\s*\(",
            code,
        )
    )
    normalized = {name.strip().rstrip("(").strip() for name in helper_names}
    return sorted(name for name in normalized if name not in allowed_helpers)


def _first_match_position(code: str, patterns: List[str]) -> Optional[int]:
    """Return the first regex match position across patterns."""
    positions = [
        match.start()
        for pattern in patterns
        for match in re.finditer(pattern, code, flags=re.DOTALL)
    ]
    return min(positions) if positions else None


def _report_facts_used_before_definition_or_load(code: str) -> bool:
    """Return whether report_facts is referenced before being defined/loaded."""
    first_use = _first_match_position(
        code,
        [
            r"\breport_facts\s*\[",
            r"\bwrite_sql_report_html\s*\([^)]*\breport_facts\b",
            r"\bsave_report_facts\s*\(\s*report_facts\s*\)",
        ],
    )
    if first_use is None:
        return False

    first_initializer = _first_match_position(
        code,
        [
            r"\breport_facts\s*=",
            r"\bload_report_facts\s*\(",
        ],
    )
    return first_initializer is None or first_initializer > first_use


def _validate_saved_sql_result_code(
    code: str,
    sql_results: List[SqlResult] | List[Dict[str, Any]],
) -> Optional[str]:
    """Reject fragile SQL result access before executing report code."""
    if not sql_results:
        return None

    import_error = _invalid_helper_import_error(code)
    if import_error:
        return import_error

    unknown_helpers = _unknown_sql_result_helpers(code)
    if unknown_helpers:
        return (
            "SQL 报告代码调用了不存在的 helper: "
            f"{', '.join(unknown_helpers)}。当前只支持 "
            "get_sql_result('SQL_RESULT_n')、get_only_sql_result()、"
            "find_sql_result_by_columns([...])、sql_result_rows(result)、"
            "require_columns(result, [...])、require_value(row, column)、"
            "to_float(value)、save_report_facts(report_facts)、"
            "load_report_facts() 和 write_sql_report_html(...)。"
        )

    ref_error = _invalid_sql_result_ref_error(code, sql_results)
    if ref_error:
        return ref_error

    if "save_report_facts(" in code and not _code_selects_saved_sql_results(code):
        return (
            "调用 save_report_facts(report_facts) 前必须在同一段代码中使用 "
            "get_sql_result('SQL_RESULT_n')、get_only_sql_result() 或 "
            "find_sql_result_by_columns([...]) 读取本轮 SQL_RESULT，并用 "
            "require_columns(...) / require_value(...) 计算 report_facts；"
            "不能空手编造并保存 report_facts。"
        )

    if _report_facts_used_before_definition_or_load(code):
        return (
            "SQL 报告代码使用 report_facts 前必须先在同一段代码中定义 "
            "report_facts = {...}，或先调用 report_facts = load_report_facts()。"
            "不能假设上一轮 code_interpreter 的 Python 变量仍然存在。"
        )

    guessed_result_patterns = [
        r"\bSQL_QUERY_RESULTS\s*\[\s*\d+\s*\]",
        r"\bdata\s*\[\s*\d+\s*\]",
    ]
    if any(re.search(pattern, code) for pattern in guessed_result_patterns):
        return (
            "SQL 报告生成代码不能用 SQL_QUERY_RESULTS[0] 或 data[0] "
            "猜测查询结果顺序。单 SQL 结果请使用 get_only_sql_result()，"
            "多 SQL 结果请使用 get_sql_result('SQL_RESULT_n') "
            "或 find_sql_result_by_columns([...]) 定位结果。"
        )

    silent_zero_patterns = [
        r"\.get\([^)]*,\s*0(?:\.0)?\s*\)",
        r"\.get\([^)]*\)\s*or\s*0(?:\.0)?",
    ]
    if any(re.search(pattern, code) for pattern in silent_zero_patterns):
        return (
            "SQL 报告生成代码不能默认置 0 或在字段缺失时静默兜底。请先用 "
            "require_columns(...) 校验结果字段，并用 require_value(row, column) "
            "读取字段；字段不存在时必须报错重试。"
        )

    if _code_writes_html_report(code) and "write_sql_report_html(" not in code:
        return (
            "SQL 报告生成不能直接 open(...html) 写文件。请先把所有用于报表"
            "展示和结论的业务事实整理成 report_facts 字典，再调用 "
            "write_sql_report_html('/tmp/report.html', html, report_facts)。"
            "HTML 中的业务数字、原因结论、建议必须来自 report_facts；"
            "本轮 SQL 未查询到的维度只能写“本轮未查询，暂不判断”。"
        )

    return None


def _normalize_html_output_path(path: str, work_dir: str) -> str:
    """Normalize an HTML output path without resolving symlinks."""
    raw_path = os.path.expanduser(path.strip())
    if not os.path.isabs(raw_path):
        raw_path = os.path.join(work_dir, raw_path)
    return os.path.abspath(raw_path)


def _extract_literal_html_paths_from_code(code: str, work_dir: str) -> List[str]:
    """Extract literal .html/.htm paths from Python code."""
    paths: List[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"""(?P<quote>["'])(?P<path>[^"'\n\r]+?\.html?)(?P=quote)""",
        code,
        flags=re.IGNORECASE,
    ):
        raw_path = match.group("path").strip()
        if not raw_path or "://" in raw_path or "{" in raw_path or "}" in raw_path:
            continue
        normalized = _normalize_html_output_path(raw_path, work_dir)
        if normalized not in seen:
            seen.add(normalized)
            paths.append(normalized)
    return paths


def _file_signature(path: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _select_existing_sql_backed_report_file(paths: List[str]) -> Optional[str]:
    """Return the most recently modified existing SQL-backed report file."""
    existing: List[tuple[int, str]] = []
    for path in paths:
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if os.path.isfile(path):
            existing.append((stat.st_mtime_ns, path))
    if not existing:
        return None
    return max(existing)[1]


def _updated_sql_backed_report_files(
    existing_files: List[str],
    candidate_paths: List[str],
    signatures_before: Dict[str, tuple[int, int] | None],
    uses_saved_sql_results: bool,
    return_code: Optional[int],
) -> List[str]:
    """Update trusted SQL-backed report files after one code execution."""
    trusted = set(existing_files)
    candidate_set = set(candidate_paths)
    if not uses_saved_sql_results:
        return sorted(trusted)

    # A SQL-backed report generation attempt invalidates stale candidates first.
    # Only a successful run that actually rewrites the file can trust it again.
    trusted.difference_update(candidate_set)
    if return_code != 0:
        return sorted(trusted)

    for html_path in candidate_paths:
        after_signature = _file_signature(html_path)
        if (
            after_signature
            and after_signature != signatures_before.get(html_path)
            and _has_report_facts_sidecar(html_path)
        ):
            trusted.add(html_path)
    return sorted(trusted)


def _sql_query_results_access_example() -> str:
    """Return the safe code pattern for reading saved SQL result rows."""
    return """result = get_only_sql_result()
# If multiple SQL results exist, use get_sql_result("SQL_RESULT_n")
# or find_sql_result_by_columns([...]) to select the intended result.
require_columns(result, ["total_value", "total_base"])
rows = sql_result_rows(result)

# Access required SQL data by column name; never guess result-list or row indexes.
total_value = sum(to_float(require_value(row, "total_value")) for row in rows)
total_base = sum(to_float(require_value(row, "total_base")) for row in rows)
rate = round(total_value / total_base * 100, 2) if total_base else 0
report_facts = {
    "total_value": total_value,
    "total_base": total_base,
    "rate": rate,
    "scope_note": "Only these facts may be used for business conclusions.",
}
save_report_facts(report_facts)
html = (
    "<div>"
    + str(report_facts["total_value"])
    + " "
    + str(report_facts["rate"])
    + "%</div>"
)
write_sql_report_html("/tmp/report.html", html, report_facts)

# If HTML generation is split into a later code_interpreter call, start that
# later call with:
# report_facts = load_report_facts()
"""


def _sql_query_results_helper_preamble() -> str:
    """Return runtime helpers injected into code_interpreter executions."""
    return """
def get_sql_result(ref):
    for result in SQL_QUERY_RESULTS:
        if result.get("ref") == ref:
            return result
    raise KeyError("SQL result ref not found: " + str(ref))


def get_only_sql_result():
    if len(SQL_QUERY_RESULTS) != 1:
        raise ValueError(
            "Multiple SQL results are available; use get_sql_result('SQL_RESULT_n') "
            "or find_sql_result_by_columns([...]) to select the intended result."
        )
    return SQL_QUERY_RESULTS[0]


def find_sql_result_by_columns(required_columns):
    required = set(required_columns)
    for result in SQL_QUERY_RESULTS:
        columns = set(result.get("columns") or [])
        if required.issubset(columns):
            return result
    raise KeyError(
        "No SQL result contains required columns: " + ", ".join(required_columns)
    )


def sql_result_rows(result):
    columns = result.get("columns") or []
    return [dict(zip(columns, row)) for row in result.get("rows", [])]


def require_columns(result, required_columns):
    columns = set(result.get("columns") or [])
    missing = [col for col in required_columns if col not in columns]
    if missing:
        raise KeyError(
            "SQL result is missing required columns: " + ", ".join(missing)
        )


def require_value(row, column_name):
    if column_name not in row:
        raise KeyError("SQL result row is missing required column: " + column_name)
    return row[column_name]


def to_float(value, default=0.0):
    if value in (None, ""):
        return default
    return float(value)


def _report_facts_path():
    return os.path.join(PLOT_DIR, "report_facts.json")


def save_report_facts(report_facts):
    if not isinstance(report_facts, dict) or not report_facts:
        raise ValueError("report_facts must be a non-empty dict")
    if not SQL_QUERY_RESULTS:
        raise ValueError("save_report_facts requires saved SQL_QUERY_RESULTS")
    facts_path = _report_facts_path()
    payload = {
        "facts": report_facts,
        "source_refs": [result.get("ref") for result in SQL_QUERY_RESULTS],
    }
    with open(facts_path, "w", encoding="utf-8") as facts_file:
        json.dump(payload, facts_file, ensure_ascii=False, indent=2, default=str)
    print("Report facts saved:", facts_path)
    return facts_path


def load_report_facts():
    facts_path = _report_facts_path()
    if not os.path.exists(facts_path):
        raise FileNotFoundError(
            "report_facts not found; compute facts from SQL_RESULT and call "
            "save_report_facts(report_facts) first"
        )
    with open(facts_path, "r", encoding="utf-8") as facts_file:
        payload = json.load(facts_file)
    if isinstance(payload, dict) and isinstance(payload.get("facts"), dict):
        return payload["facts"]
    if isinstance(payload, dict):
        return payload
    raise ValueError("report_facts file must contain a dict")


def write_sql_report_html(file_path, html, report_facts):
    if not isinstance(report_facts, dict) or not report_facts:
        raise ValueError("report_facts must be a non-empty dict")
    if not isinstance(html, str) or not html.strip():
        raise ValueError("html must be a non-empty string")
    html_path = os.path.abspath(os.path.expanduser(str(file_path)))
    with open(html_path, "w", encoding="utf-8") as html_file:
        html_file.write(html)
    facts_path = html_path + ".facts.json"
    with open(facts_path, "w", encoding="utf-8") as facts_file:
        json.dump(report_facts, facts_file, ensure_ascii=False, indent=2, default=str)
    print("SQL report written:", html_path)
    print("SQL report facts written:", facts_path)
""".strip()


def _format_sql_query_markdown(
    col_names: List[str],
    rows: List[Any],
    result_ref: str,
) -> str:
    """Format a limited SQL preview while naming the saved full result."""
    display_col_names = [_customer_facing_sql_column_label(col) for col in col_names]
    header = "| " + " | ".join(display_col_names) + " |"
    separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
    md_rows = []
    for row in rows[:50]:
        md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
    table = "\n".join([header, separator] + md_rows)
    if len(rows) > 50:
        table += f"\n\n（仅显示前 50 行，共 {len(rows)} 行）"
    table += (
        f"\n\n完整查询结果已保存为 `{result_ref}`，共 {len(rows)} 行。"
        "后续分析或生成报告时应基于该保存结果，不要只依据上方预览行。"
    )
    return table


async def _load_context_budget_config(
    llm_client: Any = None,
    model_name: Optional[str] = None,
) -> ContextBudgetConfig:
    """Build context budget config from app TOML and model metadata."""
    defaults = ContextBudgetConfig()

    def _value(agent_context: Any, field_name: str, default: Any) -> Any:
        if agent_context is None:
            return default
        value = getattr(agent_context, field_name, default)
        return default if value is None else value

    def _positive_int(value: Any) -> Optional[int]:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    agent_context = None
    try:
        app_config = CFG.SYSTEM_APP.config.configs.get("app_config")
        web_config = getattr(getattr(app_config, "service", None), "web", None)
        agent_context = getattr(web_config, "agent_context", None)
    except Exception:
        logger.debug(
            "Failed to load agent context config; using defaults", exc_info=True
        )

    configured_max_context_tokens = _positive_int(
        _value(agent_context, "max_context_tokens", None)
    )
    if configured_max_context_tokens:
        max_context_tokens = configured_max_context_tokens
    else:
        max_context_tokens = (
            await _resolve_model_context_tokens(llm_client, model_name)
            or defaults.max_context_tokens
        )

    return ContextBudgetConfig(
        max_context_tokens=max_context_tokens,
        warning_threshold=_value(
            agent_context, "warning_threshold", defaults.warning_threshold
        ),
        error_threshold=_value(
            agent_context, "error_threshold", defaults.error_threshold
        ),
        critical_threshold=_value(
            agent_context, "critical_threshold", defaults.critical_threshold
        ),
        reserved_tokens=_value(
            agent_context, "reserved_tokens", defaults.reserved_tokens
        ),
        min_keep_recent_rounds=_value(
            agent_context,
            "min_keep_recent_rounds",
            defaults.min_keep_recent_rounds,
        ),
        max_compact_failures=_value(
            agent_context,
            "max_compact_failures",
            defaults.max_compact_failures,
        ),
        max_observation_age_rounds=_value(
            agent_context,
            "max_observation_age_rounds",
            defaults.max_observation_age_rounds,
        ),
        truncated_observation_max_chars=(
            _value(
                agent_context,
                "truncated_observation_max_chars",
                defaults.truncated_observation_max_chars,
            )
        ),
        min_keep_tokens=_value(
            agent_context,
            "min_keep_tokens",
            defaults.min_keep_tokens,
        ),
    )


def _extract_auto_data_markers(text: str) -> tuple[str, Dict[str, str]]:
    """Extract generic marker blocks from script output text.

    Marker format:
        ###KEY_START###...###KEY_END###
    """

    if not text or "###" not in text:
        return text, {}

    extracted: Dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = match.group(2).strip()
        if value:
            extracted[key] = value
        return ""

    cleaned = AUTO_DATA_MARKER_PATTERN.sub(_replace, text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, extracted


async def _execute_skill_script_impl(
    skill_name: str, script_name: str, args: dict
) -> str:
    """Execute a script from a skill (implementation)."""
    skill_manager = get_skill_manager(CFG.SYSTEM_APP)
    result = await skill_manager.execute_script(skill_name, script_name, args)
    return result


@tool(
    description='执行技能中的脚本。参数: {"skill_name": "技能名称", '
    '"script_name": "脚本名称", "args": {参数}}'
)
async def execute_skill_script(skill_name: str, script_name: str, args: dict) -> str:
    """Execute a script from a skill."""
    return await _execute_skill_script_impl(skill_name, script_name, args)


@tool(
    description="获取技能资源文件内容。"
    "根据路径读取技能中的参考文档、配置文件等非脚本资源。"
    '参数: {"skill_name": "技能名称", "resource_path": "资源路径"}'
    "\\n示例:"
    '\\n- 读取参考文档: {"skill_name": "my-skill", '
    '"resource_path": "references/analysis_framework.md"}'
    "\n注意: 执行脚本请使用 shell_interpreter 工具"
)
async def get_skill_resource(
    skill_name: str, resource_path: str, args: Optional[dict] = None
) -> str:
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.get_skill_resource(skill_name, resource_path, args or {})
        return result
    except Exception as e:
        import json

        return json.dumps(
            {"error": True, "message": f"Error: {str(e)}"},
            ensure_ascii=False,
        )


@tool(
    description="执行技能scripts目录下的脚本文件。参数: "
    '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
)
async def execute_skill_script_file(
    skill_name: str, script_file_name: str, args: Optional[dict] = None
) -> str:
    """Execute a script file from a skill's scripts directory."""
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.execute_skill_script_file(
            skill_name, script_file_name, args or {}
        )
        return result
    except Exception as e:
        import json

        return json.dumps(
            {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
            ensure_ascii=False,
        )


@router.get("/v1/skills/list", response_model=Result)
async def list_skills(
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """List all available skills from the skills directory.

    Returns a list of skills with their metadata, including:
    - id: Unique identifier for the skill
    - name: Display name of the skill
    - description: Brief description of what the skill does
    - version: Skill version
    - author: Skill author
    - skill_type: Type of skill (e.g., data_analysis, chat, coding)
    - tags: List of tags for categorization
    - type: 'official' for claude/ directory, 'personal' for user/ directory
    - file_path: Relative path to the skill file
    """
    from dbgpt.agent.skill.loader import SkillLoader

    skills_data = []
    skills_dir = DEFAULT_SKILLS_DIR
    skills_dir_resolved = Path(skills_dir).expanduser().resolve()

    try:
        loader = SkillLoader()
        skills = loader.load_skills_from_directory(skills_dir, recursive=True)

        for skill in skills:
            if not skill or not skill.metadata:
                continue

            metadata = skill.metadata
            # Determine if the skill is official or personal based on file path
            file_path = getattr(metadata, "file_path", None) or ""
            if not file_path and hasattr(skill, "_config"):
                file_path = skill._config.get("file_path", "")

            # Convert absolute file_path to relative (relative to skills_dir)
            if file_path:
                try:
                    file_path = str(
                        Path(file_path)
                        .expanduser()
                        .resolve()
                        .relative_to(skills_dir_resolved)
                    )
                except Exception:
                    pass

            # Determine type based on directory structure
            skill_type_category = "official"
            if "user/" in file_path or "/user/" in file_path:
                skill_type_category = "personal"
            elif "claude/" in file_path or "/claude/" in file_path:
                skill_type_category = "official"

            # Get skill_type value
            skill_type_val = metadata.skill_type
            if hasattr(skill_type_val, "value"):
                skill_type_val = skill_type_val.value

            skill_info = {
                "id": metadata.name,
                "name": metadata.name,
                "description": metadata.description or "",
                "version": getattr(metadata, "version", "1.0.0") or "1.0.0",
                "author": getattr(metadata, "author", None),
                "skill_type": skill_type_val,
                "tags": getattr(metadata, "tags", []) or [],
                "type": skill_type_category,
                "file_path": file_path,
            }
            skills_data.append(skill_info)

        # Sort skills: official first, then by name
        skills_data.sort(key=lambda x: (0 if x["type"] == "official" else 1, x["name"]))

        return Result.succ(skills_data)
    except Exception as e:
        logger.exception("Failed to load skills from directory")
        return Result.failed(code="E5001", msg=f"Failed to load skills: {str(e)}")


@router.get("/v1/skills/detail", response_model=Result)
async def skill_detail(
    skill_name: str = Query("", description="Skill name"),
    file_path: str = Query("", description="Skill file path"),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Load a skill detail, including file tree and SKILL.md content."""
    if not file_path:
        return Result.failed(code="E4001", msg="file_path is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()

    # Always treat file_path as relative to skills_dir.
    # If an absolute path was provided (legacy), try to make it relative first.
    fp = Path(file_path).expanduser()
    if fp.is_absolute():
        try:
            fp = fp.resolve().relative_to(skills_dir)
        except Exception:
            return Result.failed(code="E4002", msg="Invalid skill file path")
    target = (skills_dir / fp).resolve()

    # Security: ensure target is under skills_dir
    try:
        target.relative_to(skills_dir)
    except Exception:
        return Result.failed(code="E4002", msg="Invalid skill file path")

    if not target.exists():
        return Result.failed(code="E4040", msg="Skill file not found")

    root_dir = target if target.is_dir() else target.parent

    def build_tree(path: Path, base: Path) -> Dict[str, Any]:
        rel = path.relative_to(base)
        node: Dict[str, Any] = {
            "title": path.name,
            "key": str(rel),
        }
        if path.is_dir():
            children = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            node["children"] = [build_tree(child, base) for child in children]
        return node

    tree = build_tree(root_dir, root_dir)

    skill_md_path = root_dir / "SKILL.md"
    frontmatter = ""
    instructions = ""
    raw_content = ""
    content_type = ""

    if skill_md_path.exists():
        raw_content = skill_md_path.read_text(encoding="utf-8")
        content_type = "skill_md"
        content = raw_content.strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                instructions = parts[2].strip()
            else:
                instructions = content
        else:
            instructions = content
    elif target.is_file():
        raw_content = target.read_text(encoding="utf-8")
        suffix = target.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            content_type = "yaml"
            frontmatter = raw_content
        elif suffix == ".json":
            content_type = "json"
            frontmatter = raw_content
        else:
            content_type = "text"
            instructions = raw_content

    metadata: Dict[str, Any] = {}
    try:
        from dbgpt.agent.skill.loader import SkillLoader

        loader = SkillLoader()
        skill = loader.load_skill_from_file(str(target))
        if skill and getattr(skill, "metadata", None):
            try:
                metadata = skill.metadata.to_dict()  # type: ignore[attr-defined]
            except Exception:
                metadata = {
                    "name": getattr(skill.metadata, "name", ""),
                    "description": getattr(skill.metadata, "description", ""),
                    "version": getattr(skill.metadata, "version", ""),
                    "author": getattr(skill.metadata, "author", ""),
                    "skill_type": getattr(skill.metadata, "skill_type", ""),
                    "tags": getattr(skill.metadata, "tags", []) or [],
                }
    except Exception:
        metadata = {}

    if not frontmatter and metadata:
        frontmatter = "\n".join(
            [
                f"name: {metadata.get('name', '')}",
                f"description: {metadata.get('description', '')}",
                f"version: {metadata.get('version', '')}",
                f"author: {metadata.get('author', '')}",
                f"skill_type: {metadata.get('skill_type', '')}",
            ]
        ).strip()

    display_path = str(target)
    display_root = str(root_dir)
    try:
        display_path = str(target.relative_to(skills_dir))
        display_root = str(root_dir.relative_to(skills_dir))
    except Exception:
        pass

    return Result.succ(
        {
            "skill_name": skill_name or metadata.get("name", ""),
            "file_path": display_path,
            "root_dir": display_root,
            "tree": tree,
            "frontmatter": frontmatter,
            "instructions": instructions,
            "raw_content": raw_content,
            "content_type": content_type,
            "metadata": metadata,
        }
    )


def _install_skill_from_dir(src_dir: Path, skill_name: str, user_dir: Path) -> str:
    """Copy an extracted skill directory into the user skills directory.

    Args:
        src_dir (Path): Directory containing the skill's files (already extracted).
        skill_name (str): Name to use for the skill directory under ``user_dir``.
        user_dir (Path): The ``skills/user/`` directory.

    Returns:
        str: Path of the installed skill directory relative to the skills root
             (i.e. ``user/<skill_name>``).
    """
    dest = user_dir / skill_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_dir, dest)
    # Return path relative to skills_dir (parent of user_dir)
    return str(dest.relative_to(user_dir.parent))


@router.post("/v1/skills/upload", response_model=Result)
async def skill_upload(
    file: UploadFile = File(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Upload a skill package (.zip, .skill) or a single file to pilot/tmp/."""
    if not file.filename:
        return Result.failed(code="E4001", msg="No file provided")

    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    try:
        filename = _validate_upload_filename(file.filename)
    except ValueError as exc:
        return Result.failed(code="E4002", msg=str(exc))

    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem

    try:
        content_bytes = await file.read()

        tmp_file = upload_dir / filename
        tmp_file.write_bytes(content_bytes)

        is_archive = False
        if suffix == ".zip":
            is_archive = True
        elif suffix == ".skill":
            buf = io.BytesIO(content_bytes)
            is_archive = zipfile.is_zipfile(buf)

        if is_archive:
            # Reuse the robust _extract_skill_from_zip helper (same one used
            # by the GitHub import endpoint) to avoid the nested-directory bug
            # that the old inline extractall logic suffered from.
            #
            # strict=False: uploaded packages may not contain a SKILL.md yet.
            tmp_zip = upload_dir / f"{uuid.uuid4().hex}.zip"
            tmp_zip.write_bytes(content_bytes)
            try:
                with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_extract:
                    dest_in_tmp = Path(tmp_extract) / "skill"
                    try:
                        dest_name = _extract_skill_from_zip(
                            tmp_zip, subpath=None, dest_dir=dest_in_tmp, strict=False
                        )
                    except ValueError as exc:
                        return Result.failed(code="E4002", msg=str(exc))

                    rel_path = _install_skill_from_dir(dest_in_tmp, dest_name, user_dir)
            finally:
                tmp_zip.unlink(missing_ok=True)

        else:
            dest = user_dir / stem
            dest.mkdir(parents=True, exist_ok=True)

            if suffix in (".md", ".skill"):
                target_name = "SKILL.md"
            else:
                target_name = filename
            target_file = dest / target_name

            target_file.write_bytes(content_bytes)

            rel_path = str(dest.relative_to(skills_dir))

        return Result.succ(
            {
                "file_path": rel_path,
                "tmp_path": str(tmp_file),
                "message": f"Skill uploaded successfully: {rel_path}",
            }
        )
    except Exception as e:
        logger.exception("Failed to upload skill")
        return Result.failed(code="E5002", msg=f"Upload failed: {str(e)}")


def _parse_github_url(
    github_url: str,
) -> "tuple[str, str, str, Optional[str]]":
    """Parse a GitHub or skills.sh URL into (owner, repo, branch, subdir).

    Supported formats:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/<branch>[/optional/sub/dir]
      - https://github.com/owner/repo/blob/<branch>/path/to/FILE.md
      - https://skills.sh/owner/repo
      - https://skills.sh/owner/repo[/skill-name]

    Returns:
        tuple[str, str, str, Optional[str]]
          (owner, repo, branch, subdir) — branch is always a str (defaults to "main")

    Raises:
        ValueError: if the URL is not a recognisable GitHub/skills.sh repo URL.
    """
    parsed = urlparse(github_url)
    is_skills_sh = parsed.netloc in ("skills.sh", "www.skills.sh")
    is_github = parsed.netloc in ("github.com", "www.github.com")

    if not is_github and not is_skills_sh:
        raise ValueError(f"Not a GitHub URL: {github_url!r}")

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from URL: {github_url!r}")

    owner, repo = parts[0], parts[1]
    # Strip '.git' suffix if present
    if repo.endswith(".git"):
        repo = repo[:-4]

    branch: str = "main"
    subdir: Optional[str] = None

    if is_skills_sh:
        # skills.sh: /owner/repo[/skill-name[/more]]
        # Everything after owner/repo is treated as subpath
        if len(parts) >= 3:
            subdir = "/".join(parts[2:])
    else:
        # GitHub
        if len(parts) >= 4 and parts[2] == "tree":
            # /owner/repo/tree/<branch>[/path/to/subdir]
            branch = parts[3]
            if len(parts) >= 5:
                subdir = "/".join(parts[4:])
        elif len(parts) >= 4 and parts[2] == "blob":
            # /owner/repo/blob/<branch>/path/to/FILE.md — strip filename
            branch = parts[3]
            if len(parts) >= 6:
                # Keep everything except the last component (the filename)
                subdir = "/".join(parts[4:-1])
            # If exactly 5 parts: blob/<branch>/filename — no subdir

    return owner, repo, branch, subdir


def _construct_download_url(owner: str, repo: str, branch: str) -> str:
    """Return the GitHub archive ZIP download URL for the given branch.

    Args:
        owner (str): Repository owner/organisation.
        repo (str): Repository name.
        branch (str): Branch name.

    Returns:
        str: URL pointing to the ZIP archive for the branch.
    """
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"


def _is_macos_junk(name: str) -> bool:
    """Return True if the archive entry is a macOS metadata artifact."""
    parts = name.split("/")
    return any(p == "__MACOSX" or p.startswith("._") for p in parts)


def _extract_skill_from_zip(
    zip_path: "Path",
    subpath: "Optional[str]",
    dest_dir: "Path",
    strict: bool = True,
) -> str:
    """Extract a skill from a ZIP archive into ``dest_dir``.

    The ZIP is expected to have a single top-level directory (e.g.
    ``repo-main/``).  That top-level directory is stripped when extracting so
    that the files inside it land directly in ``dest_dir``.

    When ``subpath`` is given, only the files under
    ``{top_dir}/{subpath}/`` are extracted (again, stripped to ``dest_dir``).

    macOS metadata entries (``__MACOSX/`` directories and ``._*`` files) are
    automatically filtered out before any directory-structure analysis so they
    do not cause spurious nested directories.

    Args:
        zip_path (Path): Path to the ZIP file on disk.
        subpath (Optional[str]): Relative sub-directory inside the archive
            (after stripping the top-level dir) that contains the skill.
            Pass ``None`` to use the root of the archive.
        dest_dir (Path): Directory into which the skill files are extracted.
            It is created if it does not exist; if it already exists its
            contents are removed before extraction.
        strict (bool): When ``True`` (default), raise ``ValueError`` if no
            ``SKILL.md`` is found in the archive.  When ``False``, skip the
            ``SKILL.md`` validation — useful for uploading generic skill
            packages that may not yet contain a ``SKILL.md``.

    Returns:
        str: The skill name derived from ``subpath`` (last component) or from
        the top-level archive directory name.

    Raises:
        ValueError: If the archive contains path-traversal sequences.
        ValueError: If no ``SKILL.md`` is found after extraction (only when
            ``strict=True``).
        ValueError: If the archive root contains multiple sub-directories with
            ``SKILL.md`` files and no ``subpath`` was specified (the error
            message lists the available sub-directory names).
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()

        # Security: reject any path-traversal entries
        for name in all_names:
            normalized = os.path.normpath(name)
            if normalized.startswith("..") or ".." in normalized.split(os.sep):
                raise ValueError(f"Unsafe path in archive: {name!r}")

        # Filter out macOS metadata artifacts before analysing structure
        valid_names = [n for n in all_names if not _is_macos_junk(n)]

        # Detect the single top-level directory (GitHub archives always have one)
        top_dirs = {n.split("/")[0] for n in valid_names if "/" in n}
        archive_root: Optional[str] = top_dirs.pop() if len(top_dirs) == 1 else None

        # Build the prefix inside the archive that maps to dest_dir
        if subpath:
            skill_prefix = (
                f"{archive_root}/{subpath}/" if archive_root else f"{subpath}/"
            )
            skill_name = subpath.split("/")[-1]
        else:
            skill_prefix = f"{archive_root}/" if archive_root else ""
            skill_name = archive_root or dest_dir.name

        # Check whether SKILL.md exists under the chosen prefix
        skill_md_entry = next(
            (n for n in valid_names if n == skill_prefix + "SKILL.md"),
            None,
        )

        if skill_md_entry is None and not subpath:
            # No SKILL.md at root — scan one level of subdirectories
            subdirs_with_skill = []
            for name in valid_names:
                if not name.startswith(skill_prefix):
                    continue
                rel = name[len(skill_prefix) :]
                parts = rel.split("/")
                if len(parts) == 2 and parts[1] == "SKILL.md":
                    subdirs_with_skill.append(parts[0])

            if len(subdirs_with_skill) > 1:
                raise ValueError(
                    "Multiple skills found. Specify a subpath. "
                    "Available: " + ", ".join(sorted(subdirs_with_skill))
                )

            # If exactly one sub-directory has SKILL.md, use it automatically
            if len(subdirs_with_skill) == 1:
                only_subdir = subdirs_with_skill[0]
                skill_prefix = f"{skill_prefix}{only_subdir}/"
                skill_name = only_subdir
                skill_md_entry = skill_prefix + "SKILL.md"

        if strict and skill_md_entry is None:
            raise ValueError(
                "No SKILL.md found in the archive"
                + (f" under '{subpath}'" if subpath else "")
                + ". Make sure the skill directory contains a SKILL.md file."
            )

        # Prepare dest_dir: remove existing content then (re-)create
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Extract valid members individually (no extractall) for security
        for member in valid_names:
            if not member.startswith(skill_prefix) or member == skill_prefix:
                continue
            rel = member[len(skill_prefix) :]
            if not rel:
                continue
            target = dest_dir / rel
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))

    return skill_name


@router.post("/v1/skills/import_github", response_model=Result)
async def skill_import_from_github_v2(
    request: Request,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Import a skill from a GitHub or skills.sh URL.

    Accepts ``{ "url": "..." }`` from the frontend, downloads the repository
    ZIP, extracts the skill, installs it to ``skills/user/<name>/``, and
    returns a success response.

    This endpoint:

    - Accepts a raw JSON body ``{ "url": "..." }`` (no Pydantic model).
    - Supports branch fallback: tries ``main`` first, then ``master`` if 404.
    - Enforces a 50 MB download size limit.
    - Delegates extraction/installation to the modular helpers
      ``_extract_skill_from_zip`` and ``_install_skill_from_dir``.

    Error codes:
        - ``E4001``: Empty URL.
        - ``E4003``: Malformed or non-GitHub/skills.sh URL.
        - ``E4004``: ``SKILL.md`` not found in the downloaded content.
        - ``E4005``: Download failed or size limit exceeded.
        - ``E5002``: Unexpected server-side error.
    """
    import httpx

    # --- parse JSON body --------------------------------------------------------
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return Result.failed(code="E4001", msg="URL must not be empty")

    # --- parse URL --------------------------------------------------------------
    try:
        owner, repo, branch, subpath = _parse_github_url(url)
    except ValueError as exc:
        return Result.failed(code="E4003", msg=str(exc))

    # --- resolve dirs -----------------------------------------------------------
    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    # --- download with branch fallback (main → master) --------------------------
    zip_path: Optional[Path] = None
    tmp_dir_obj = None  # tempfile.TemporaryDirectory kept alive until finally

    try:
        zip_url = _construct_download_url(owner, repo, branch)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(120.0),
        ) as client:
            response = await client.get(zip_url)

            # Branch fallback: if the resolved branch gives 404, try "master"
            if response.status_code == 404 and branch == "main":
                fallback_branch = "master"
                fallback_url = _construct_download_url(owner, repo, fallback_branch)
                response = await client.get(fallback_url)
                if response.status_code == 200:
                    branch = fallback_branch
                    zip_url = fallback_url

            if response.status_code != 200:
                return Result.failed(
                    code="E4005",
                    msg=(
                        f"Failed to download {zip_url!r}: HTTP {response.status_code}"
                    ),
                )

            content_bytes = response.content

        # --- size limit check ---------------------------------------------------
        if len(content_bytes) > 50 * 1024 * 1024:
            return Result.failed(
                code="E4005",
                msg=(
                    f"Download size {len(content_bytes) // (1024 * 1024)} MB "
                    "exceeds the 50 MB limit"
                ),
            )

        # --- save raw zip to tmp ------------------------------------------------
        zip_filename = f"{repo}-{branch}.zip"
        zip_path = upload_dir / zip_filename
        zip_path.write_bytes(content_bytes)

        # --- extract into a temp directory, then install ------------------------
        tmp_dir_obj = tempfile.TemporaryDirectory(dir=upload_dir)
        dest_dir_in_temp = Path(tmp_dir_obj.name) / "skill"
        dest_dir_in_temp.mkdir(parents=True, exist_ok=True)

        try:
            skill_name = _extract_skill_from_zip(zip_path, subpath, dest_dir_in_temp)
        except ValueError as exc:
            err_msg = str(exc)
            if "SKILL.md" in err_msg:
                return Result.failed(code="E4004", msg=err_msg)
            return Result.failed(code="E4003", msg=err_msg)

        rel_path = _install_skill_from_dir(dest_dir_in_temp, skill_name, user_dir)

        return Result.succ(
            {
                "file_path": rel_path,
                "message": f"Skill imported successfully from GitHub: {rel_path}",
            }
        )

    except httpx.RequestError as exc:
        logger.exception("Network error while downloading skill from GitHub")
        return Result.failed(
            code="E4005", msg=f"Network error downloading skill: {str(exc)}"
        )
    except Exception as exc:
        logger.exception("Failed to import skill from GitHub (v2)")
        return Result.failed(code="E5002", msg=f"Import failed: {str(exc)}")
    finally:
        # Clean up temp zip file
        if zip_path is not None:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
        # Clean up temp extraction directory
        if tmp_dir_obj is not None:
            try:
                tmp_dir_obj.cleanup()
            except Exception:
                pass


def _sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _react_agent_stream_impl(
    dialogue: ConversationVo,
    cache_conv_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    import asyncio

    from dbgpt.agent import AgentContext, AgentMemory, AgentMessage
    from dbgpt.agent.claude_skill import get_registry, load_skills_from_dir
    from dbgpt.agent.core.memory.gpts import (
        DefaultGptsPlansMemory,
        GptsMemory,
    )
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.react_agent import ReActAgent
    from dbgpt.agent.resource import ToolPack, tool
    from dbgpt.agent.resource.base import AgentResource, ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager
    from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
    from dbgpt.agent.util.react_parser import ReActOutputParser
    from dbgpt.core import (
        ModelMessage,
        ModelMessageRoleType,
        ModelRequest,
        StorageConversation,
    )
    from dbgpt.model.cluster.client import DefaultLLMClient
    from dbgpt.util.code.server import get_code_server
    from dbgpt_app.openapi.api_v1.html_repair import repair_html_if_needed
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory
    from dbgpt_serve.conversation.serve import Serve as ConversationServe

    step = 0
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        user_input = str(user_input or "")

    file_path = None
    knowledge_space = None
    skill_name = None
    database_name = None
    if dialogue.ext_info and isinstance(dialogue.ext_info, dict):
        file_path = dialogue.ext_info.get("file_path")
        skill_name = dialogue.ext_info.get("skill_name")
        # Support multiple field names for knowledge space
        knowledge_space = (
            dialogue.ext_info.get("knowledge_space")
            or dialogue.ext_info.get("knowledge_space_name")
            or dialogue.ext_info.get("knowledge_space_id")
        )
        database_name = dialogue.ext_info.get("database_name")

    step_started_at: Dict[str, float] = {}
    round_thinking_started_at: Dict[int, float] = {}
    round_thinking_finished_at: Dict[int, float] = {}

    def build_step(title: str, detail: str, phase: str = None):
        nonlocal step
        step += 1
        step_id = f"step-{step}"
        step_started_at[step_id] = time.monotonic()
        event_data = {
            "type": "step.start",
            "step": step,
            "id": step_id,
            "title": title,
            "detail": detail,
        }
        if phase:
            event_data["phase"] = phase
        return step_id, _sse_event(event_data)

    def step_output(detail: str):
        return _sse_event({"type": "step.output", "step": step, "detail": detail})

    def step_chunk(step_id: str, output_type: str, content: Any):
        safe_content = (
            content
            if str(output_type).lower() == "html"
            else _sanitize_customer_facing_answer(content)
        )
        return _sse_event(
            {
                "type": "step.chunk",
                "id": step_id,
                "output_type": output_type,
                "content": safe_content,
            }
        )

    def step_elapsed_ms(step_id: str) -> Optional[int]:
        started_at = step_started_at.get(step_id)
        if started_at is None:
            return None
        return max(0, int((time.monotonic() - started_at) * 1000))

    def thinking_elapsed_ms(round_num: Optional[int]) -> Optional[int]:
        if round_num is None:
            return None
        started_at = round_thinking_started_at.get(round_num)
        finished_at = round_thinking_finished_at.get(round_num)
        if started_at is None or finished_at is None:
            return None
        return max(0, int((finished_at - started_at) * 1000))

    def apply_step_timing(
        step_id: str,
        target: Dict[str, Any],
        round_num: Optional[int] = None,
    ) -> None:
        elapsed_ms = step_elapsed_ms(step_id)
        thought_ms = thinking_elapsed_ms(round_num)
        if elapsed_ms is not None:
            target["elapsed_ms"] = elapsed_ms
        if thought_ms is not None:
            target["thinking_elapsed_ms"] = thought_ms
        if elapsed_ms is not None:
            target["execution_elapsed_ms"] = max(
                0,
                elapsed_ms - (thought_ms or 0),
            )

    def step_done(
        step_id: str,
        status: str = "done",
        round_num: Optional[int] = None,
    ):
        payload = {"type": "step.done", "id": step_id, "status": status}
        apply_step_timing(step_id, payload, round_num=round_num)
        return _sse_event(payload)

    def step_meta(
        step_id: str,
        thought: Optional[str],
        action: Optional[str],
        action_input: Optional[str],
        title: Optional[str] = None,
        action_intention: Optional[str] = None,
        action_reason: Optional[str] = None,
        todo_meta: Optional[Dict[str, Any]] = None,
    ):
        safe_thought = _sanitize_customer_facing_answer(thought)
        safe_action_intention = _sanitize_customer_facing_answer(action_intention)
        safe_action_reason = _sanitize_customer_facing_answer(action_reason)
        safe_action_input = _sanitize_customer_facing_action_input(
            action,
            action_input,
        )
        payload = {
            "type": "step.meta",
            "id": step_id,
            "thought": safe_thought,
            "action_intention": safe_action_intention,
            "action_reason": safe_action_reason,
            "action": action,
            "action_input": safe_action_input,
            "title": title,
        }
        if todo_meta:
            payload["todo_meta"] = todo_meta
        return _sse_event(payload)

    def chunk_text(text: str, max_len: int = 800) -> List[str]:
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + max_len])
            start += max_len
        return chunks

    def emit_tool_chunks(step_id: str, content: Any) -> List[str]:
        raw_chunks: List[str] = []
        if content is None:
            return raw_chunks
        parsed = None
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("chunks"), list):
            for item in parsed["chunks"]:
                if not isinstance(item, dict):
                    continue
                output_type = item.get("output_type") or "text"
                payload = item.get("content")
                if output_type in ["code", "markdown"] and isinstance(payload, str):
                    # Send code and markdown as a single chunk — never split it.
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
                elif output_type in ["text"] and isinstance(payload, str):
                    for chunk in chunk_text(payload, max_len=800):
                        raw_chunks.append(step_chunk(step_id, output_type, chunk))
                else:
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
            return raw_chunks
        if isinstance(content, str) and content:
            for chunk in chunk_text(content, max_len=800):
                raw_chunks.append(step_chunk(step_id, "text", chunk))
        return raw_chunks

    def normalize_display_text(value: Optional[str]) -> Optional[str]:
        """Normalize a model-provided display field."""
        if not value:
            return None

        text = re.sub(r"\s+", " ", value).strip()
        text = re.sub(
            r"^(phase|status|状态|action\s+intention|action\s+reason)\s*:\s*",
            "",
            text,
            flags=re.I,
        ).strip()
        text = text.strip(" .,:;，。；：")
        if not text:
            return None
        return text

    def summarize_thought(
        thought: Optional[str], action: Optional[str] = None
    ) -> Optional[str]:
        """Fallback compressor when the model does not provide a short status."""
        if not thought:
            return None

        text = re.sub(r"\s+", " ", thought).strip()
        text = re.sub(r"^(thought|phase)\s*:\s*", "", text, flags=re.I).strip()
        if not text:
            return None

        split_markers = [
            r"\baction\b\s*:",
            r"\bobservation\b\s*:",
            r"\bphase\b\s*:",
            r"\bnow i need to\b",
            r"\bnext,?\b",
            r"\bthen\b",
            r"现在需要",
            r"下一步",
            r"接下来",
            r"然后",
        ]
        marker_pattern = "|".join(split_markers)
        text = re.split(marker_pattern, text, maxsplit=1, flags=re.I)[0].strip(
            " .,:;，。；："
        )

        prefixes = [
            "the user wants me to ",
            "i need to ",
            "i should ",
            "let me ",
            "i will ",
            "现在我需要",
            "我需要",
            "接下来我需要",
            "让我",
            "现在开始",
            "好的，",
            "好，",
        ]
        lowered = text.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix.lower()):
                text = text[len(prefix) :].strip(" .,:;，。；：")
                lowered = text.lower()
                break

        action_lower = (action or "").lower()
        if action_lower == "sql_query":
            return "正在查询数据库信息"
        if action_lower == "code_interpreter":
            return "正在生成分析代码"
        if action_lower == "html_interpreter":
            return "正在生成并渲染 HTML 报告"
        if action_lower == "todowrite":
            return "正在更新任务计划"
        if action_lower in {"execute_skill_script", "execute_skill_script_file"}:
            return "正在执行分析脚本"

        return text

    skills_dir = DEFAULT_SKILLS_DIR
    registry = get_registry()

    # Step 1: Pre-load skills
    load_skills_from_dir(skills_dir, recursive=True)
    all_skills = registry.list_skills()

    # Step 2: Get business tools from ResourceManager
    rm = get_resource_manager(CFG.SYSTEM_APP)
    business_tools: List[Any] = []
    try:
        # Get all registered tool resources from ResourceManager
        tool_resources = rm._type_to_resources.get("tool", [])
        for reg_resource in tool_resources:
            if reg_resource.resource_instance is not None:
                business_tools.append(reg_resource.resource_instance)
    except Exception:
        pass  # If no business tools, continue with empty list

    # Step 3: Load knowledge space resource if specified in ext_info
    knowledge_resources: List[Any] = []
    knowledge_context = ""
    if knowledge_space:
        try:
            from dbgpt_serve.agent.resource.knowledge import (
                KnowledgeSpaceRetrieverResource,
            )

            knowledge_resource = KnowledgeSpaceRetrieverResource(
                name=f"knowledge_space_{knowledge_space}",
                space_name=knowledge_space,
                top_k=4,
                system_app=CFG.SYSTEM_APP,
            )
            knowledge_resources.append(knowledge_resource)
            knowledge_context = f"""
## Knowledge Base
- Knowledge space: {knowledge_resource.retriever_name or knowledge_space}
- Description: {knowledge_resource.retriever_desc or "Knowledge retrieval available"}
- You can use the 'knowledge_retrieve' tool to search this knowledge base.
"""
            logger.info(
                f"Loaded knowledge space resource: {knowledge_space} "
                f"(name: {knowledge_resource.retriever_name})"
            )
        except Exception as e:
            logger.warning(f"Failed to load knowledge space resource: {e}", exc_info=e)
            knowledge_context = f"""
## Knowledge Base
- Warning: Failed to load knowledge space '{knowledge_space}'. Error: {str(e)}
"""

    # Step 4: Load database connector if specified in ext_info
    database_connector = None
    database_context = ""
    if database_name:
        try:
            local_db_manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
            database_connector = local_db_manager.get_connector(database_name)
            table_names = list(database_connector.get_table_names())
            table_info = database_connector.get_table_info_no_throw()
            database_context = _build_database_context(
                database_name=database_name,
                user_question=user_input,
                table_names=table_names,
                table_info=table_info,
            )
            logger.info(
                f"Loaded database connector: {database_name} "
                f"(tables: {', '.join(table_names)})"
            )
        except Exception as e:
            logger.warning(f"Failed to load database connector: {e}", exc_info=e)
            database_context = f"""
## 数据库
- 警告: 加载数据库 '{database_name}' 失败。错误: {str(e)}
"""

    react_state: Dict[str, Any] = {
        "skills_loaded": True,  # Skills are pre-loaded now
        "matched": None,
        "skill_prompt": None,
        "file_path": file_path,
    }

    # Pre-select skill if skill_name provided in ext_info
    pre_matched_skill = None
    if skill_name:
        pre_matched_skill = registry.get_skill(skill_name)
        if not pre_matched_skill:
            # Try case-insensitive match
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    pre_matched_skill = registry.get_skill(s.name)
                    break
        if pre_matched_skill:
            react_state["matched"] = pre_matched_skill
            react_state["skill_prompt"] = pre_matched_skill.get_prompt()
            logger.info(f"Pre-selected skill from ext_info: {skill_name}")

    # Build skills_context based on whether skill is pre-selected
    if pre_matched_skill:
        # User specified a skill: show only the selected skill
        skills_context = (
            f"- {pre_matched_skill.metadata.name}: "
            f"{pre_matched_skill.metadata.description}"
        )
    else:
        # User did not specify a skill: show all available skills
        skills_context = (
            "\n".join([f"- {s.name}: {s.description}" for s in all_skills])
            if all_skills
            else "No skills available."
        )

    def _mentions_excel(text: str) -> bool:
        lowered = text.lower()
        keywords = [
            "excel",
            "xlsx",
            "xls",
            "spreadsheet",
            "workbook",
            "sheet",
            "工作表",
            "表格",
            "电子表格",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _is_excel_skill(meta) -> bool:
        name = (meta.name or "").lower()
        desc = (meta.description or "").lower()
        tags = [tag.lower() for tag in (meta.tags or [])]
        return any(
            token in name or token in desc or token in tags
            for token in ["excel", "xlsx", "xls", "spreadsheet"]
        )

    @tool(
        description="Select the most relevant skill based on user query from the "
        "available skills list in system prompt."
    )
    def select_skill(query: str) -> str:
        match_input = query or ""
        if react_state.get("file_path"):
            match_input = f"{match_input} excel xlsx spreadsheet file"
        matched = registry.match_skill(match_input)
        if (
            matched
            and _is_excel_skill(matched.metadata)
            and not (_mentions_excel(query) or react_state.get("file_path"))
        ):
            matched = None
        react_state["matched"] = matched
        if matched:
            detail = (
                f"Matched: {matched.metadata.name} - {matched.metadata.description}"
            )
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": detail}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "No skill matched; proceed without skill",
                    }
                ]
            },
            ensure_ascii=False,
        )

    @tool(
        description="Load skill content by skill name and file path. "
        "Returns the SKILL.md content of the specified skill. "
        '参数: {"skill_name": "技能名称", "file_path": "技能文件路径"}'
    )
    def load_skill(skill_name: str, file_path: str = "") -> str:
        """Load the skill content (SKILL.md) by skill name and file path.

        Args:
            skill_name: The name of the skill to load.
            file_path: The file path of the skill.
        """
        from dbgpt.agent.claude_skill import get_registry

        # Try to get skill from registry
        registry = get_registry()
        matched = registry.get_skill(skill_name)

        # If not found, try case-insensitive match
        if not matched:
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    matched = registry.get_skill(s.name)
                    break

        if not matched:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Skill '{skill_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Update react_state for compatibility with existing logic
        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()
        resolved_file_path = _resolve_skill_file_path(
            skill_name=skill_name,
            file_path=file_path,
            all_skills=all_skills,
            skills_dir=skills_dir,
        )

        # Build response content
        chunks = [
            {
                "output_type": "text",
                "content": f"Skill: {matched.metadata.name}",
            },
            {
                "output_type": "text",
                "content": f"File path: {resolved_file_path or 'unknown'}",
            },
            {"output_type": "text", "content": "---"},
        ]

        # Add skill content/prompt
        if matched.instructions:
            chunks.append({"output_type": "markdown", "content": matched.instructions})
        elif matched.prompt_template:
            prompt_text = (
                matched.prompt_template.template
                if hasattr(matched.prompt_template, "template")
                else str(matched.prompt_template)
            )
            chunks.append({"output_type": "markdown", "content": prompt_text})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Load uploaded file info if provided.")
    def load_file() -> str:
        if not react_state.get("file_path"):
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file uploaded"}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {"output_type": "text", "content": react_state["file_path"]},
                    {
                        "output_type": "text",
                        "content": "File path provided by user upload",
                    },
                ]
            },
            ensure_ascii=False,
        )

    @tool(description="Execute quick analysis on uploaded Excel/CSV file.")
    async def execute_analysis() -> str:
        matched = react_state.get("matched")
        if not react_state.get("file_path"):
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file to analyze"}]},
                ensure_ascii=False,
            )
        if matched and not _is_excel_skill(matched.metadata):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Selected skill is not for Excel analysis",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        code_server = await get_code_server(CFG.SYSTEM_APP)
        analysis_code = """
import json
import pandas as pd

file_path = r"{file_path}"
if file_path.lower().endswith((".xls", ".xlsx")):
    df = pd.read_excel(file_path)
else:
    df = pd.read_csv(file_path)
summary = {{
    "shape": list(df.shape),
    "columns": list(df.columns),
    "dtypes": {{col: str(dtype) for col, dtype in df.dtypes.items()}},
    "head": df.head(5).to_dict(orient="records"),
}}
print(json.dumps(summary, ensure_ascii=False))
""".format(file_path=react_state["file_path"])
        result = await code_server.exec(analysis_code, "python")
        output_text = (
            result.output.decode("utf-8") if isinstance(result.output, bytes) else ""
        )
        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": analysis_code.strip()}
        ]
        if output_text:
            try:
                summary = json.loads(output_text)
                chunks.append({"output_type": "json", "content": summary})
                head_rows = summary.get("head")
                columns = summary.get("columns")
                if isinstance(head_rows, list) and isinstance(columns, list):
                    chunks.append(
                        {
                            "output_type": "table",
                            "content": {
                                "columns": [
                                    {"title": col, "dataIndex": col, "key": col}
                                    for col in columns
                                ],
                                "rows": head_rows,
                            },
                        }
                    )
                numeric_columns = [
                    col
                    for col, dtype in (summary.get("dtypes") or {}).items()
                    if "int" in dtype or "float" in dtype
                ]
                if numeric_columns and isinstance(head_rows, list):
                    series_col = numeric_columns[0]
                    data = [
                        {"x": idx + 1, "y": row.get(series_col)}
                        for idx, row in enumerate(head_rows)
                        if row.get(series_col) is not None
                    ]
                    if data:
                        chunks.append(
                            {
                                "output_type": "chart",
                                "content": {
                                    "data": data,
                                    "xField": "x",
                                    "yField": "y",
                                },
                            }
                        )
            except Exception:
                chunks.append({"output_type": "text", "content": output_text})
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Resolve required tools for the selected skill.")
    def load_tools() -> str:
        matched = react_state.get("matched")
        rm = get_resource_manager(CFG.SYSTEM_APP)
        required_tools = matched.metadata.required_tools if matched else []
        if not required_tools:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No required tools specified",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        loaded = []
        failed = []
        for tool_name in required_tools:
            try:
                rm.build_resource_by_type(
                    ResourceType.Tool.value,
                    AgentResource(type=ResourceType.Tool.value, value=tool_name),
                )
                loaded.append(tool_name)
            except Exception as e:
                failed.append(f"{tool_name} ({e})")
        chunks = []
        if loaded:
            chunks.append(
                {"output_type": "text", "content": f"Loaded: {', '.join(loaded)}"}
            )
        if failed:
            chunks.append(
                {"output_type": "text", "content": f"Failed: {', '.join(failed)}"}
            )
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Execute a tool by name with JSON args.")
    async def execute_tool(tool_name: str, args: dict) -> str:
        rm = get_resource_manager(CFG.SYSTEM_APP)
        try:
            tool_resource = rm.build_resource_by_type(
                ResourceType.Tool.value,
                AgentResource(type=ResourceType.Tool.value, value=tool_name),
            )
            tool_pack = ToolPack([tool_resource])
            result = await tool_pack.async_execute(resource_name=tool_name, **args)
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": str(result)}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Tool execute failed: {e}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description="Retrieve relevant information from the knowledge base. "
        "Use this tool when the user question involves content that may be "
        'in the knowledge base. Parameters: {{"query": "search query"}}'
    )
    async def knowledge_retrieve(query: str) -> str:
        if not knowledge_resources:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No knowledge base available",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        resource = knowledge_resources[0]
        try:
            chunks = await resource.retrieve(query)
            if chunks:
                content = "\n".join(
                    [f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks[:5])]
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Retrieved {len(chunks)} relevant documents"
                                ),
                            },
                            {"output_type": "markdown", "content": content},
                        ]
                    },
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Knowledge retrieval failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description=(
            "对用户选择的 PostgreSQL 数据库执行 SQL 查询（仅支持单条 SELECT 或 "
            "WITH ... SELECT）。必须使用 PostgreSQL 方言，并且只能使用表结构中"
            "真实存在的表名和字段名。"
            '参数: {"sql": "SELECT 语句"}'
        )
    )
    def sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the selected database."""
        if database_connector is None:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper().lstrip()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"安全限制: 不允许执行 {kw} 语句，"
                                    f"仅支持 SELECT 查询。"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        table_policy_error = _validate_bus_table_policy_sql(
            database_name=database_name,
            user_question=user_input,
            sql=sql_stripped,
        )
        if table_policy_error:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": table_policy_error,
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            result = database_connector.run(sql_stripped)
            if not result:
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            # result[0] = column names, result[1:] = data rows
            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = _mask_sensitive_sql_rows(col_names, result[1:])
            sql_results = react_state.setdefault("sql_query_results", [])
            result_ref = f"SQL_RESULT_{len(sql_results) + 1}"
            sql_results.append(
                SqlResult(
                    columns=col_names,
                    rows=[list(row) for row in rows],
                    row_count=len(rows),
                    sql=sql_stripped,
                )
            )

            table = _format_sql_query_markdown(col_names, rows, result_ref)

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    def _try_repair_truncated_code(raw_code: str) -> Optional[str]:
        """Attempt to fix code that was truncated by the LLM's token limit.

        Common symptoms: unterminated string literals, unclosed brackets/parens.
        Strategy:
          1. Remove the last (likely incomplete) logical line.
          2. Close any remaining open brackets / parentheses.
          3. Re-compile. If it passes, return the repaired code.
        Returns None if repair is not possible.
        """

        lines = raw_code.split("\n")
        # Try progressively removing trailing lines (up to 10) to find a
        # clean cut-off point.
        for trim in range(1, min(11, len(lines))):
            candidate_lines = lines[: len(lines) - trim]
            if not candidate_lines:
                continue
            candidate = "\n".join(candidate_lines)

            # Strip any trailing incomplete string by trying to tokenize
            # and removing broken tail tokens.
            # Close unmatched brackets/parens/braces
            open_chars = {"(": ")", "[": "]", "{": "}"}
            close_chars = set(open_chars.values())
            stack: list = []
            for ch in candidate:
                if ch in open_chars:
                    stack.append(open_chars[ch])
                elif ch in close_chars:
                    if stack and stack[-1] == ch:
                        stack.pop()

            # Append closing chars in reverse order
            if stack:
                candidate += "\n" + "".join(reversed(stack))

            try:
                compile(candidate, "<repair>", "exec")
                return candidate
            except SyntaxError:
                continue
        return None

    @tool(
        description="Execute Python code for data analysis and computation. "
        "Supports pandas, numpy, matplotlib, json, os, etc. "
        "Use this tool when you need to run Python code to process data, "
        "generate charts, or perform calculations. "
        "Saved SQL query results are available as SQL_QUERY_RESULTS and "
        "SQL_RESULTS_PATH. "
        'Parameters: {{"code": "python code string"}}'
    )
    async def code_interpreter(code: str) -> str:
        """Execute arbitrary Python code and return stdout/stderr.

        Runs in a subprocess using the project's Python interpreter,
        so all installed packages (pandas, numpy, etc.) are available.
        CRITICAL: Each call is completely independent — variables do NOT
        persist between calls except injected SQL_QUERY_RESULTS/SQL_RESULTS_PATH.
        Every code snippet MUST include all necessary data loading
        (e.g. df = pd.read_csv(FILE_PATH)) and processing.
        Never assume df or any other variable already exists.
        Always print() results you want to see in the output.
        """
        import asyncio
        import shutil
        import sys
        import uuid

        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No code provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Use persistent work dir under pilot/tmp/{conv_id} so files
        # survive across calls and can be referenced later (e.g. in HTML).
        cid = react_state.get("conv_id") or "default"
        work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(work_dir, exist_ok=True)
        sql_results_path = os.path.join(work_dir, "sql_query_results.json")
        sql_results_for_run = react_state.get("sql_query_results", [])
        uses_saved_sql_results = _code_uses_saved_sql_results(
            code,
            sql_results_for_run,
        )
        if uses_saved_sql_results:
            code_guard_error = _validate_saved_sql_result_code(
                code,
                sql_results_for_run,
            )
            if code_guard_error:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": code_guard_error,
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        html_candidate_paths = _extract_literal_html_paths_from_code(code, work_dir)
        default_report_path = _normalize_html_output_path(
            os.path.join(tempfile.gettempdir(), "report.html"),
            work_dir,
        )
        if default_report_path not in html_candidate_paths:
            html_candidate_paths.append(default_report_path)
        html_signatures_before = {
            path: _file_signature(path) for path in html_candidate_paths
        }
        try:
            with open(sql_results_path, "w", encoding="utf-8") as sql_file:
                json.dump(
                    _serialize_sql_results_for_code(
                        sql_results_for_run
                    ),
                    sql_file,
                    ensure_ascii=False,
                    default=str,
                )
        except Exception:
            logger.debug("Failed to write SQL result refs for code", exc_info=True)

        # Collect image files that existed BEFORE this run
        IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        pre_existing_images: set = set()
        for root, _dirs, files in os.walk(work_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    pre_existing_images.add(os.path.join(root, f))

        preamble_lines = [
            "import json",
            "import os",
            "import builtins",
            "builtins.os = os",
            "import pandas as pd",
            "import numpy as np",
            f'PLOT_DIR = r"{work_dir}"',
            "os.makedirs(PLOT_DIR, exist_ok=True)",
            f'SQL_RESULTS_PATH = r"{sql_results_path}"',
            "if os.path.exists(SQL_RESULTS_PATH):",
            "    with open(SQL_RESULTS_PATH, 'r', encoding='utf-8') as _sql_file:",
            "        SQL_QUERY_RESULTS = json.load(_sql_file)",
            "else:",
            "    SQL_QUERY_RESULTS = []",
        ]
        preamble_lines.extend(_sql_query_results_helper_preamble().splitlines())
        fp = react_state.get("file_path")
        if fp:
            preamble_lines.append(f'FILE_PATH = r"{fp}"')
        preamble = "\n".join(preamble_lines) + "\n"
        full_code = preamble + code

        try:
            compile(full_code, "<code_interpreter>", "exec")
        except SyntaxError as se:
            # Attempt auto-repair for truncated code (common with long LLM
            # outputs that hit the token limit).
            repaired = _try_repair_truncated_code(full_code)
            if repaired is not None:
                logger.warning(
                    "code_interpreter: auto-repaired truncated code "
                    f"(original SyntaxError: {se.msg} line {se.lineno})"
                )
                full_code = repaired
                # Strip the preamble back out for the "code" display chunk
                code = full_code[len(preamble) :]
            else:
                error_msg = (
                    f"SyntaxError before execution: {se.msg} "
                    f"(line {se.lineno})\n"
                    "Please regenerate complete, syntactically valid Python "
                    "code. Keep code under 80 lines and split long tasks "
                    "into multiple code_interpreter calls."
                )
                react_state["sql_backed_report_files"] = (
                    _updated_sql_backed_report_files(
                        existing_files=react_state.get(
                            "sql_backed_report_files", []
                        ),
                        candidate_paths=html_candidate_paths,
                        signatures_before=html_signatures_before,
                        uses_saved_sql_results=uses_saved_sql_results,
                        return_code=1,
                    )
                )
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "code", "content": code.strip()},
                            {"output_type": "text", "content": error_msg},
                        ]
                    },
                    ensure_ascii=False,
                )

        proc_return_code: Optional[int] = None
        try:
            tmp_path = os.path.join(work_dir, "_run.py")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                tmp.write(full_code)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            proc_return_code = proc.returncode
            output_text = stdout.decode("utf-8", errors="replace")
            error_text = stderr.decode("utf-8", errors="replace")

            if proc_return_code != 0 and error_text:
                output_text = (
                    output_text + "\n[ERROR]\n" + error_text
                    if output_text
                    else error_text
                )
        except asyncio.TimeoutError:
            proc_return_code = 1
            output_text = "Execution timed out (60s limit)"
        except Exception as e:
            proc_return_code = 1
            output_text = f"Execution error: {e}"

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            clean_output = output_text.strip()
            max_out_len = 2000
            if len(clean_output) > max_out_len:
                truncation_notice = (
                    f"\n\n... [Output truncated, length: {len(clean_output)} chars."
                    f" Only showing first {max_out_len} chars."
                    f" If you generated HTML, the file is saved.]"
                )
                clean_output = clean_output[:max_out_len] + truncation_notice
            chunks.append({"output_type": "text", "content": clean_output})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output — add print() to see results)",
                }
            )

        # Scan work_dir recursively for NEW image files generated by this run
        try:
            os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    if ext in IMAGE_EXTS and full_path not in pre_existing_images:
                        unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                        dest = os.path.join(STATIC_MESSAGE_IMG_PATH, unique_name)
                        shutil.copy2(full_path, dest)
                        img_url = f"/images/{unique_name}"
                        chunks.append(
                            {
                                "output_type": "image",
                                "content": img_url,
                            }
                        )
                        # Track generated images in react_state for
                        # html_interpreter to reference later
                        react_state.setdefault("generated_images", []).append(img_url)
        except Exception:
            pass

        # Clean up the temp script file but keep work_dir for persistence
        try:
            script_path = os.path.join(work_dir, "_run.py")
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

        # Append a summary of ALL generated images so far, so the LLM
        # has a clear reference when generating HTML later.
        all_images = react_state.get("generated_images", [])
        if all_images:
            img_summary = "已生成的图片URL（在生成HTML时请使用这些URL）:\n" + "\n".join(
                f"  - {url}" for url in all_images
            )
            chunks.append({"output_type": "text", "content": img_summary})

        if uses_saved_sql_results:
            react_state["sql_backed_report_files"] = (
                _updated_sql_backed_report_files(
                    existing_files=react_state.get("sql_backed_report_files", []),
                    candidate_paths=html_candidate_paths,
                    signatures_before=html_signatures_before,
                    uses_saved_sql_results=uses_saved_sql_results,
                    return_code=proc_return_code,
                )
            )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="Execute shell/bash commands in a sandboxed environment. "
        "Use this tool when you need to run shell commands such as ls, cat, "
        "grep, curl, apt, pip, git, or any other CLI tool. "
        "The sandbox provides resource limits (256MB memory, 30s timeout) "
        "and process isolation. "
        'Parameters: {"code": "shell command(s) to execute"}'
    )
    async def shell_interpreter(code: str) -> str:
        """Execute shell/bash commands in a sandboxed environment.

        Uses dbgpt-sandbox LocalRuntime to run bash scripts with:
        - Memory limit: 256MB
        - Timeout: 30 seconds
        - Process tree management (cleanup on timeout/error)
        - Security validation (blocks dangerous patterns like rm -rf /)
        Each call is independent — no state persists between calls.
        """
        import os
        import uuid

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No command provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            from dbgpt_sandbox.sandbox.execution_layer.base import (
                ExecutionStatus,
                SessionConfig,
            )
            from dbgpt_sandbox.sandbox.execution_layer.local_runtime import (
                LocalRuntime,
            )
        except ImportError:
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "code", "content": code.strip()},
                        {
                            "output_type": "text",
                            "content": (
                                "Error: sandbox runtime package is not installed."
                            ),
                        },
                    ]
                },
                ensure_ascii=False,
            )

        session_id = f"bash_{uuid.uuid4().hex[:12]}"
        runtime = LocalRuntime()

        from dbgpt.configs.model_config import ROOT_PATH

        sandbox_work_dir = ROOT_PATH
        os.makedirs(sandbox_work_dir, exist_ok=True)

        config = SessionConfig(
            language="bash",
            working_dir=sandbox_work_dir,
            max_memory=256 * 1024 * 1024,  # 256MB
            timeout=30,
        )

        output_text = ""
        try:
            session = await runtime.create_session(session_id, config)
            result = await session.execute(code)

            if result.status == ExecutionStatus.SUCCESS:
                output_text = result.output or ""
            elif result.status == ExecutionStatus.TIMEOUT:
                output_text = f"Execution timed out ({config.timeout}s limit)"
            else:
                output_text = result.error or "Unknown execution error"
                if result.output:
                    output_text = result.output + "\n[ERROR]\n" + output_text
        except Exception as e:
            output_text = f"Sandbox execution error: {e}"
        finally:
            try:
                await runtime.destroy_session(session_id)
            except Exception:
                pass

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            chunks.append({"output_type": "text", "content": output_text.strip()})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output)",
                }
            )

        # ── Safety-net post-processing for skill script execution ──
        # If the LLM used shell_interpreter to run a skill script despite
        # the prompt requesting execute_skill_script_file, we still capture
        # critical side-effects (ratio_data, images) into react_state.
        _code_lower = code.strip().lower()
        _is_skill_script = "skills/" in _code_lower and ".py" in _code_lower
        if _is_skill_script and output_text.strip():
            import shutil

            from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

            # 1) Capture calculate_ratios.py output as ratio_data
            if "calculate_ratios" in _code_lower:
                try:
                    ratio_data = json.loads(output_text.strip())
                    if isinstance(ratio_data, dict):
                        react_state["ratio_data"] = ratio_data
                        logger.info(
                            "shell_interpreter: captured %d ratio_data keys",
                            len(ratio_data),
                        )
                except Exception:
                    pass

            # 2) Capture generate_charts.py output — look for image paths
            #    and copy them to static dir, same as execute_skill_script_file
            if "generate_charts" in _code_lower:
                try:
                    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                    # Try to parse JSON output for image paths
                    try:
                        chart_output = json.loads(output_text.strip())
                        if isinstance(chart_output, dict):
                            # Might be {"charts": {...}} or flat dict
                            chart_map = chart_output.get("charts", chart_output)
                            for name, abs_path in chart_map.items():
                                if isinstance(abs_path, str) and os.path.isfile(
                                    abs_path
                                ):
                                    ext = os.path.splitext(abs_path)[1].lower()
                                    if ext in IMAGE_EXTS:
                                        unique_name = (
                                            f"{uuid.uuid4().hex[:8]}_"
                                            f"{os.path.basename(abs_path)}"
                                        )
                                        dest = os.path.join(
                                            STATIC_MESSAGE_IMG_PATH, unique_name
                                        )
                                        shutil.copy2(abs_path, dest)
                                        img_url = f"/images/{unique_name}"
                                        react_state.setdefault(
                                            "generated_images", []
                                        ).append(img_url)
                                        orig_stem = os.path.splitext(
                                            os.path.basename(abs_path)
                                        )[0].lower()
                                        react_state.setdefault("image_url_map", {})[
                                            orig_stem
                                        ] = img_url
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # Also scan the output dir for any new .png files
                    cid = react_state.get("conv_id") or "default"
                    from dbgpt.configs.model_config import PILOT_PATH

                    out_dir = os.path.join(PILOT_PATH, "tmp", cid)
                    if os.path.isdir(out_dir):
                        for fname in os.listdir(out_dir):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in IMAGE_EXTS:
                                abs_path = os.path.join(out_dir, fname)
                                orig_stem = os.path.splitext(fname)[0].lower()
                                if orig_stem not in react_state.get(
                                    "image_url_map", {}
                                ):
                                    unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                                    dest = os.path.join(
                                        STATIC_MESSAGE_IMG_PATH, unique_name
                                    )
                                    shutil.copy2(abs_path, dest)
                                    img_url = f"/images/{unique_name}"
                                    react_state.setdefault(
                                        "generated_images", []
                                    ).append(img_url)
                                    react_state.setdefault("image_url_map", {})[
                                        orig_stem
                                    ] = img_url
                    # Append image URL summary for LLM reference
                    all_images = react_state.get("generated_images", [])
                    if all_images:
                        img_summary = (
                            "\u5df2\u751f\u6210\u7684\u56fe\u7247URL\uff08\u5728\u751f\u6210HTML\u62a5\u544a\u65f6\u8bf7\u4f7f\u7528\u8fd9\u4e9bURL\uff09:\n"
                            + "\n".join(f"  - {url}" for url in all_images)
                        )
                        chunks.append({"output_type": "text", "content": img_summary})
                    logger.info(
                        "shell_interpreter: captured %d images for skill script",
                        len(react_state.get("image_url_map", {})),
                    )
                except Exception as e:
                    logger.warning(
                        "shell_interpreter: image post-processing failed: %s", e
                    )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="执行技能scripts目录下的脚本文件。参数: "
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
    )
    async def execute_skill_script_file(
        skill_name: str, script_file_name: str, args: Optional[dict] = None
    ) -> str:
        """Execute a script file from a skill's scripts directory.

        After execution, any new image files (.png, .jpg, etc.) generated
        by the script are automatically copied to the static images directory
        and their URLs are returned in the output chunks.
        """
        import shutil
        import uuid

        from dbgpt.agent.skill.manage import get_skill_manager
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        try:
            from dbgpt.configs.model_config import PILOT_PATH

            sm = get_skill_manager(CFG.SYSTEM_APP)
            cid = react_state.get("conv_id") or "default"
            out_dir = os.path.join(PILOT_PATH, "tmp", cid)
            os.makedirs(out_dir, exist_ok=True)
            # Auto-inject the correct file path from react_state into args.
            # The LLM sometimes corrupts the uploaded file path (e.g. changing
            # 'dbgpt-app' to 'dbgpt_app'), so we override any file-path-like
            # keys in args with the known-good path from react_state.
            real_file_path = react_state.get("file_path")
            if real_file_path and args:
                _FILE_PATH_KEYS = {
                    "input_file",
                    "file_path",
                    "data_path",
                    "csv_path",
                    "excel_path",
                    "data_file",
                }
                for key in list(args.keys()):
                    if key in _FILE_PATH_KEYS:
                        args[key] = real_file_path
            result_str = await sm.execute_skill_script_file(
                skill_name,
                script_file_name,
                args or {},
                output_dir=out_dir,
            )

            # Read script source code and prepend as a 'code' chunk
            # so the frontend can display it in the left pane.
            try:
                _skill_path = sm._get_skill_path(skill_name)
                _sf = script_file_name.lstrip("/\\")
                if _sf.startswith("scripts/") or _sf.startswith("scripts\\"):
                    _sf = _sf[8:]
                _script_abs = os.path.join(_skill_path, "scripts", _sf)
                with open(_script_abs, "r", encoding="utf-8") as _f:
                    _script_source = _f.read()
            except Exception:
                _script_source = None

            # Post-process: copy image files to static dir and replace
            # absolute paths with /images/ URLs.
            try:
                result_obj = json.loads(result_str)
                chunks = result_obj.get("chunks", [])
                # Prepend script source code as a 'code' chunk
                if _script_source:
                    chunks.insert(
                        0,
                        {
                            "output_type": "code",
                            "content": _script_source,
                        },
                    )
                os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                for chunk in chunks:
                    if chunk.get("output_type") == "image":
                        abs_path = chunk["content"]
                        if os.path.isabs(abs_path) and os.path.isfile(abs_path):
                            ext = os.path.splitext(abs_path)[1].lower()
                            if ext in IMAGE_EXTS:
                                unique_name = (
                                    f"{uuid.uuid4().hex[:8]}_"
                                    f"{os.path.basename(abs_path)}"
                                )
                                dest = os.path.join(
                                    STATIC_MESSAGE_IMG_PATH, unique_name
                                )
                                shutil.copy2(abs_path, dest)
                                img_url = f"/images/{unique_name}"
                                chunk["content"] = img_url
                                react_state.setdefault("generated_images", []).append(
                                    img_url
                                )
                                # Also store a map: original filename (no ext)
                                # -> served URL for template placeholder
                                # resolution.
                                orig_stem = os.path.splitext(
                                    os.path.basename(abs_path)
                                )[0].lower()
                                react_state.setdefault("image_url_map", {})[
                                    orig_stem
                                ] = img_url

                # Append image URL summary for LLM reference
                all_images = react_state.get("generated_images", [])
                if all_images:
                    img_summary = (
                        "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                        + "\n".join(f"  - {url}" for url in all_images)
                    )
                    chunks.append({"output_type": "text", "content": img_summary})
                auto_data = react_state.get("auto_data")
                if not isinstance(auto_data, dict):
                    auto_data = {}
                    react_state["auto_data"] = auto_data
                filtered_chunks = []
                for chunk in chunks:
                    if chunk.get("output_type") != "text":
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""
                    cleaned, extracted = _extract_auto_data_markers(content)
                    if extracted:
                        auto_data.update(extracted)
                        logger.info(
                            "execute_skill_script_file: captured auto_data keys=%s",
                            sorted(extracted.keys()),
                        )
                    if cleaned:
                        chunk["content"] = cleaned
                        filtered_chunks.append(chunk)
                    elif not extracted:
                        filtered_chunks.append(chunk)
                chunks = filtered_chunks

                # Compatibility path for existing financial-report skill.
                if script_file_name == "calculate_ratios.py":
                    for chunk in chunks:
                        if chunk.get("output_type") == "text":
                            try:
                                ratio_data = json.loads(chunk["content"])
                                react_state["ratio_data"] = ratio_data
                            except Exception:
                                pass
                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            except (json.JSONDecodeError, KeyError):
                return result_str
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
                ensure_ascii=False,
            )

    @tool(
        description="将 HTML 渲染为可交互的网页报告，这是向用户展示网页报告的唯一方式。"
        "【数据报告】如果报告包含 sql_query 查询数据，必须先用 code_interpreter "
        "使用 get_only_sql_result()、get_sql_result('SQL_RESULT_n') "
        "或 find_sql_result_by_columns([...]) 读取已保存 SQL 结果，"
        "计算指标并写入 HTML 文件，"
        "再调用本工具的文件模式："
        '{"file_path": "/tmp/report.html", "title": "报告标题"}。'
        "【普通 HTML】不包含 SQL 数据的简单页面可以直接传入完整 HTML 字符串："
        '{"html": "<html>...</html>", "title": "报告标题"}。'
        "你需要自己生成完整的 HTML 代码"
        "（包含 <!DOCTYPE html>、<html>、<head>、<body> 等），"
        "然后传给 html 参数即可。"
        "HTML 可以很长，没有长度限制，不需要分段传入。"
        "【技能模式 - 仅在使用技能时可选】如果正在使用技能（skill），可以用模板模式："
        '{"template_path": "技能名/templates/模板.html", '
        '"data": {"KEY": "值"}, "title": "标题"}。'
        '也可以用文件模式：{"file_path": "/path/to/report.html"}'
    )
    async def html_interpreter(
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: dict | str = None,
    ) -> str:
        """Render HTML as an interactive web report.

        Default usage: pass a complete HTML string via the `html` parameter.
        The HTML can be arbitrarily long — no length limit, no chunking needed.

        Skill template mode (optional): pass `template_path` (relative to skills
        dir) plus a `data` dict whose keys match {{PLACEHOLDER}} tokens in the
        template. The backend reads the template and performs all replacements.

        SQL-backed report mode: `file_path` reads HTML generated by
        code_interpreter from saved SQL results.
        """
        import os
        import re

        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        sql_backed_report_file = False

        # ── Mode 1: template_path + data ──────────────────────────────
        if template_path and template_path.strip():
            tp = template_path.strip()
            skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
            target = (skills_dir / tp).resolve()
            # Security: must be under skills_dir
            try:
                target.relative_to(skills_dir)
            except ValueError:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Invalid template_path: {tp}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if not target.is_file():
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Template not found: {tp}. "
                                    "This skill does not have HTML templates. "
                                    "Please retry by calling html_interpreter "
                                    "with the `html` parameter instead — "
                                    "generate the complete HTML report code "
                                    "yourself and pass it directly via "
                                    '{"html": "<html>...</html>", '
                                    '"title": "report title"}.'
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            try:
                raw_template = target.read_text(encoding="utf-8")
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading template: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # Replace {{KEY}} placeholders with values from data dict
            # Sometimes the LLM passes data as a JSON string instead of a dict
            replacements = data
            if isinstance(replacements, str):
                try:
                    replacements = json.loads(replacements)
                except Exception as e:
                    logger.warning(
                        f"html_interpreter failed to parse string data as json: {e}"
                    )
                    # Attempt to fix truncated JSON by appending closing
                    # braces/quotes
                    try:
                        fixed = str(replacements).rstrip()
                        if not fixed.endswith("}"):
                            if fixed.endswith('"'):
                                fixed += "}"
                            else:
                                fixed += '"}'
                        replacements = json.loads(fixed)
                    except Exception:
                        replacements = {}
            if not isinstance(replacements, dict):
                replacements = {}
            auto_data = react_state.get("auto_data", {})
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}

            # Merge LLM replacements with ratio_data from calculate_ratios.py
            ratio_data = react_state.get("ratio_data", {})
            if isinstance(ratio_data, dict):
                # auto_data / LLM data overwrites ratio_data if keys overlap
                merged = {**ratio_data, **replacements}
                replacements = merged

            # Auto-resolve CHART_* placeholders from generated images.
            # image_url_map: {
            #     "financial_overview": "/images/abc_financial_overview.png"
            # }
            # Template uses:
            #     {{CHART_FINANCIAL_OVERVIEW}}
            #     -> /images/abc_financial_overview.png
            image_url_map = react_state.get("image_url_map", {})
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():
                    chart_key = f"CHART_{stem.upper()}"
                    if chart_key not in replacements:
                        replacements[chart_key] = url

            def _replace_placeholder(m):
                key = m.group(1)
                return str(replacements.get(key, ""))

            html = re.sub(r"\{\{([A-Z_0-9]+)\}\}", _replace_placeholder, raw_template)
            if not title or title == "Report":
                title = target.stem
            logger.info(
                "html_interpreter: template=%s, %d placeholders replaced, "
                "html=%d chars",
                tp,
                len(replacements),
                len(html),
            )

        # ── Mode 2: file_path ─────────────────────────────────────────
        elif file_path and file_path.strip():
            fp = file_path.strip()
            if not os.path.isfile(fp):
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))
                if os.path.isfile(alt):
                    fp = alt
                else:
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    html = f.read()
                if not title or title == "Report":
                    title = os.path.splitext(os.path.basename(fp))[0]
                normalized_fp = _normalize_html_output_path(fp, os.getcwd())
                sql_backed_report_file = normalized_fp in set(
                    react_state.get("sql_backed_report_files", [])
                )
                logger.info(
                    "html_interpreter: read %d chars from file %s",
                    len(html),
                    fp,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading file: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        # ── Mode 3: inline html ──────────────────────────────────────
        # Unescape literal \n sequences that LLM may produce.
        # IMPORTANT: Only apply this unescape when html was provided directly
        # (inline mode).  Template mode (Mode 1) and file mode (Mode 2) produce
        # real HTML that already contains actual newlines and may contain JS
        # regex literals like /\\n/ which must NOT be collapsed into real
        # newlines — doing so corrupts the JS and breaks chart rendering.
        if html and isinstance(html, str) and not template_path and not file_path:
            if "\\n" in html:
                html = html.replace("\\n", "\n")
            if "\\t" in html:
                html = html.replace("\\t", "\t")
        if not html or not html.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No HTML content provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        async def _ai_repair_html(raw_html, validation):
            if len(raw_html) > 120_000:
                logger.warning(
                    "html_interpreter: skip AI HTML repair for large input, "
                    "html=%d chars",
                    len(raw_html),
                )
                return None

            model_name = dialogue.model_name
            if not model_name:
                try:
                    models = await llm_client.models()
                    model_name = models[0].model if models else None
                except Exception as e:
                    logger.warning("html_interpreter: list models failed: %s", e)
                    return None
            if not model_name:
                return None

            issues = "; ".join(validation.issues[:30]) or "invalid_html"
            prompt = (
                "Repair the generated HTML document below so it is a complete, "
                "valid, renderable HTML document. Preserve the report content, "
                "visual design, scripts, styles, image paths, and data values. "
                "Fix missing required tags, malformed closing tags, unclosed "
                "tags, and unsafe control characters only. Return only the "
                "complete repaired HTML, with no markdown fences or explanation.\n\n"
                f"Validation issues: {issues}\n"
                f"Report title: {title or 'Report'}\n\n"
                "<ORIGINAL_HTML>\n"
                f"{raw_html}\n"
                "</ORIGINAL_HTML>"
            )
            try:
                request = ModelRequest.build_request(
                    model=model_name,
                    messages=[
                        ModelMessage(
                            role=ModelMessageRoleType.SYSTEM,
                            content=(
                                "You repair generated HTML. You must output only "
                                "one complete HTML document."
                            ),
                        ),
                        ModelMessage(
                            role=ModelMessageRoleType.HUMAN,
                            content=prompt,
                        ),
                    ],
                    temperature=0.0,
                    max_new_tokens=min(dialogue.max_new_tokens or 8192, 8192),
                )
                output = await llm_client.generate(request)
                if output.success and output.has_text:
                    return output.text
                logger.warning(
                    "html_interpreter: AI HTML repair failed, error_code=%s",
                    output.error_code,
                )
            except Exception as e:
                logger.warning("html_interpreter: AI HTML repair failed: %s", e)
            return None

        # Post-process: fix image URLs that the LLM may have guessed wrong.
        # Files in STATIC_MESSAGE_IMG_PATH are named "{uuid8}_{original}.ext".
        # The LLM might reference "/images/original.ext" (without UUID prefix)
        # or even just "original.ext".  Build a lookup and replace.
        fixed_html = html.strip()
        # LLMs sometimes persist escaped closing tags like <\/style> or
        # <\/script>. In iframe srcDoc, browsers do not treat those as real
        # closing tags, so the report can be swallowed as CSS/JS text.
        fixed_html = re.sub(
            r"<\\+\s*/\s*([A-Za-z][A-Za-z0-9:-]*)\s*>",
            r"</\1>",
            fixed_html,
            flags=re.IGNORECASE,
        )
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            # Map: lowercase base name (without uuid prefix) -> served path
            # e.g. "monthly_sales_trend.png"
            #      -> "/images/a1b2c3ff_monthly_sales_trend.png"
            name_to_served: Dict[str, str] = {}
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTS:
                        continue
                    # Strip the 8-char hex UUID prefix + underscore
                    # Pattern: <8 hex chars>_<original_name>
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)
                    if m:
                        base_name = m.group(1).lower()
                        served_path = f"/images/{fname}"
                        # Keep the latest (last alphabetically = most recent
                        # UUID)
                        name_to_served[base_name] = served_path

            if name_to_served:
                # Replace patterns like:
                #   src="/images/monthly_sales_trend.png"
                #   src="images/monthly_sales_trend.png"
                #   src="monthly_sales_trend.png"
                # with the correct served path.
                def _fix_img_src(match: re.Match) -> str:
                    prefix = match.group(1)  # src=" or src='
                    raw_path = match.group(2)  # the path value
                    quote = match.group(3)  # closing quote

                    # Extract just the filename from the path
                    filename = raw_path.rsplit("/", 1)[-1].lower()

                    # Check if it's already a correct served path
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):
                        return match.group(0)  # Already has UUID prefix

                    if filename in name_to_served:
                        return f"{prefix}{name_to_served[filename]}{quote}"
                    return match.group(0)  # No match, keep original

                # Match src="..." or src='...' containing image references
                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])"""
                    r"""([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))"""
                    r"""(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass  # If post-processing fails, use original HTML

        # Auto-append images generated during this session that the LLM
        # forgot to include in the HTML.
        try:
            gen_images = react_state.get("generated_images", [])
            if gen_images:
                # Extract all image filenames already referenced in the HTML
                # (e.g. "time_series_trend.png" from any src="...time_series_trend.png")
                html_img_stems = set(
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

                # An image is "missing" only when neither its exact URL nor its
                # stem (filename with UUID prefix stripped) is already covered.
                def _img_stem(url):
                    return re.sub(r"^[0-9a-f]+_", "", os.path.basename(url))

                missing = [
                    url
                    for url in gen_images
                    if url not in fixed_html and _img_stem(url) not in html_img_stems
                ]
                if missing:
                    imgs_html = "".join(
                        f'<div style="margin:16px 0">'
                        f'<img src="{url}" '
                        f'style="max-width:100%;height:auto;'
                        f'border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (
                        '<div style="margin-top:32px">'
                        "<h2>📊 分析图表</h2>"
                        f"{imgs_html}</div>"
                    )
                    # Insert before </body> if present, otherwise append
                    if "</body>" in fixed_html.lower():
                        fixed_html = re.sub(
                            r"(</body>)",
                            section + r"\1",
                            fixed_html,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        fixed_html += section
        except Exception:
            pass

        fixed_html = await repair_html_if_needed(
            fixed_html,
            title=title,
            ai_repair=_ai_repair_html,
        )

        sql_results = react_state.get("sql_query_results", [])
        if sql_backed_report_file:
            logger.info(
                "html_interpreter: skip strict number validation for "
                "SQL-backed report file"
            )
        else:
            validation = validate_html_report_data(fixed_html, sql_results)
            if not validation.ok:
                logger.warning(
                    "html_interpreter: blocked untraceable report data: %s",
                    "; ".join(validation.issues),
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    "报告数据未通过真实性校验，已阻止渲染。"
                                    "以下数值无法追溯到本轮 SQL 查询结果"
                                    "或可计算派生值："
                                    + "、".join(validation.untraceable_values[:20])
                                    + "。\n\n"
                                    "请按以下步骤修正：\n"
                                    "1. 用 code_interpreter 通过 "
                                    "get_only_sql_result()、"
                                    "get_sql_result('SQL_RESULT_n') 或 "
                                    "find_sql_result_by_columns([...]) "
                                    "读取已保存 SQL 结果\n"
                                    "2. 从已保存 SQL 结果中计算所有指标"
                                    "（总计、比率等），不要硬编码任何数字；"
                                    "把所有报表业务事实放入 report_facts\n"
                                    "3. 用 report_facts 生成 HTML，并调用 "
                                    "write_sql_report_html 写入 /tmp/report.html\n"
                                    "4. 调用 "
                                    'html_interpreter(file_path="/tmp/report.html")'
                                    " 渲染\n\n"
                                    "示例：\n"
                                    "```python\n"
                                    "result = find_sql_result_by_columns("
                                    "['total_value', 'total_base'])\n"
                                    "require_columns(result, "
                                    "['total_value', 'total_base'])\n"
                                    "rows = sql_result_rows(result)\n"
                                    "# 按列名读取必需字段，不要猜 data[0] 或 row[15]；"
                                    "字段不存在必须报错重试，不能默认置 0\n"
                                    "total_value = sum(to_float(require_value("
                                    "row, 'total_value')) for row in rows)\n"
                                    "total_base = sum(to_float(require_value("
                                    "row, 'total_base')) for row in rows)\n"
                                    "rate = round(total_value / total_base * 100, 2) "
                                    "if total_base else 0\n"
                                    "report_facts = {'total_value': total_value, "
                                    "'total_base': total_base, 'rate': rate}\n"
                                    "html = '<div>' + str(report_facts['total_value']) "
                                    "+ ' ' + str(report_facts['rate'])"
                                    " + '%</div>'\n"
                                    "write_sql_report_html('/tmp/report.html', "
                                    "html, report_facts)\n"
                                    "```"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        chunks: List[Dict[str, Any]] = [
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    llm_client = DefaultLLMClient(
        CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create(),
        auto_convert_message=True,
    )
    # If user specified a model_name, use Priority strategy to ensure the
    # agent uses the requested model instead of picking the first available one.
    if dialogue.model_name:
        llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,
            strategy_context=json.dumps([dialogue.model_name]),
        )
    else:
        llm_config = LLMConfig(llm_client=llm_client)

    conv_id = cache_conv_id or dialogue.conv_uid or str(uuid.uuid4())
    react_state["conv_id"] = conv_id

    def _create_memory():
        gpt_memory = GptsMemory(
            plans_memory=DefaultGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )
        gpt_memory.init(conv_id, enable_vis_message=False)
        return gpt_memory

    gpt_memory = REACT_AGENT_MEMORY_CACHE.get_or_create(conv_id, _create_memory)
    agent_memory = AgentMemory(gpts_memory=gpt_memory)

    # --- Persist conversation to chat_history for sidebar display ---
    conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
    storage_conv = StorageConversation(
        conv_uid=conv_id,
        chat_mode=dialogue.chat_mode or "chat_react_agent",
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        summary=dialogue.user_input,
        app_code=dialogue.app_code,
        conv_storage=conv_serve.conv_storage,
        message_storage=conv_serve.message_storage,
    )
    storage_conv.save_to_storage()
    storage_conv.start_new_round()
    storage_conv.add_user_message(user_input)
    context = AgentContext(
        conv_id=conv_id,
        gpts_app_code="react_agent",
        gpts_app_name="ReAct",
        language="zh",
        temperature=dialogue.temperature or 0.2,
        max_new_tokens=dialogue.max_new_tokens or 8192,
        enable_context_management=True,
    )

    # Build file context if file uploaded
    file_context = ""
    if file_path:
        file_context = f"""
## User Uploaded File
- File path: {file_path}
- Analyze this file if needed for the user's request.
"""

    # Build skill context for system prompt when skill is pre-selected
    skill_prompt_context = ""
    execution_instruction = ""
    if pre_matched_skill and react_state.get("skill_prompt"):
        skill_template = react_state["skill_prompt"]
        skill_text = (
            skill_template.template
            if hasattr(skill_template, "template")
            else str(skill_template)
        )
        skill_prompt_context = f"""
## 已加载技能指令（{pre_matched_skill.metadata.name}）
以下是用户选择的技能的完整指令，请严格按照这些指令进行操作：

{skill_text}
"""
        execution_instruction = f"""
## 执行要求
1. 用户已明确选择技能：{pre_matched_skill.metadata.name}
2. 你必须严格按照上述技能指令的步骤执行
3. 阅读技能指令，理解每一步需要调用的工具
4. 按顺序执行工具调用，完成技能目标
"""

    # ── TodoWrite tool ──────────────────────────────────────────────────
    # A session-level task list that the agent maintains.  The full list is
    # replaced on every call (same semantics as OpenCode's todowrite).
    # The tool pushes a ``plan.update`` SSE event so the frontend can
    # render a live task-plan card.
    _todo_list: List[Dict[str, str]] = []

    @tool(
        description=(
            "Create and manage a structured task list for the current session. "
            "Use this tool to plan complex tasks (3+ steps), track progress, "
            "and show the user what you are doing. "
            "Pass the FULL todo list every time (not incremental). "
            "Each todo has: content (brief description), "
            "status (pending | in_progress | completed | cancelled), "
            "priority (high | medium | low). "
            "Rules: only ONE task in_progress at a time; mark tasks completed "
            "immediately after finishing; do NOT use for single trivial tasks."
            '\nParameter: {"todos": [{"content": "...", "status": "...", '
            '"priority": "..."}]}'
        )
    )
    def todowrite(todos: str) -> str:
        """Update the session todo list (full replacement)."""
        import json as _json

        parsed: List[Dict[str, str]] = []
        try:
            raw = _json.loads(todos) if isinstance(todos, str) else todos
            items = raw if isinstance(raw, list) else raw.get("todos", raw)
            if isinstance(items, list):
                for item in items:
                    parsed.append(
                        {
                            "content": str(item.get("content", "")),
                            "status": str(item.get("status", "pending")),
                            "priority": str(item.get("priority", "medium")),
                        }
                    )
        except Exception:
            return _json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Error: invalid todos JSON",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        _todo_list.clear()
        _todo_list.extend(parsed)

        total = len(parsed)
        done = sum(1 for t in parsed if t["status"] == "completed")
        return _json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": f"Todo list updated: {done}/{total} completed",
                    }
                ],
                # Attach the todo list so SSE handler can forward it
                "__todos__": parsed,
            },
            ensure_ascii=False,
        )

    _todo_action_history: Dict[int, List[str]] = {}

    def _active_todo_index() -> Optional[int]:
        for idx, item in enumerate(_todo_list):
            if item.get("status") == "in_progress":
                return idx
        return None

    def _normalize_text(value: Optional[str]) -> str:
        return (value or "").strip().lower()

    def _is_report_like(text: str) -> bool:
        keywords = [
            "report",
            "html",
            "dashboard",
            "visual",
            "visualization",
            "图表",
            "报告",
            "报表",
            "可视化",
            "渲染",
            "展示",
        ]
        return any(keyword in text for keyword in keywords)

    def _looks_like_raw_sql(text: str) -> bool:
        """Check if text looks like raw SQL output rather than a summary."""
        t = text.strip().upper()
        sql_prefixes = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "WITH")
        if any(t.startswith(p) for p in sql_prefixes):
            return True
        # Heuristic: mostly ASCII with SQL keywords
        if len(text) > 50 and re.search(
            r"\b(FROM|WHERE|GROUP BY|ORDER BY|JOIN)\b", t
        ):
            return True
        return False

    def _looks_like_html(text: str) -> bool:
        """Check if text looks like an HTML document."""
        t = text.strip()
        if not t:
            return False
        # Check for common HTML indicators
        if t.startswith("<!DOCTYPE") or t.startswith("<!doctype"):
            return True
        if t.startswith("<html") or t.startswith("<HTML"):
            return True
        if "<html" in t[:500].lower() and "</html>" in t.lower():
            return True
        return False

    def _extract_html_document(text: str) -> Optional[str]:
        """Extract an HTML document from plain text or fenced markdown."""
        stripped = text.strip()
        if _looks_like_html(stripped):
            return stripped

        for match in re.finditer(
            r"```(?:html)?\s*(.*?)```",
            stripped,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            candidate = match.group(1).strip()
            if _looks_like_html(candidate):
                return candidate

        match = re.search(
            r"(?is)(<!doctype\s+html\b.*?</html>|<html\b.*?</html>)",
            stripped,
        )
        if match:
            return match.group(1).strip()
        return None

    def _extract_html_from_tool_result(value: Any, depth: int = 0) -> Optional[str]:
        """Extract real HTML from nested tool-result JSON strings/chunks."""
        if depth > 4 or value is None:
            return None
        if isinstance(value, dict):
            chunks = value.get("chunks")
            if isinstance(chunks, list):
                for item in chunks:
                    html = _extract_html_from_tool_result(item, depth + 1)
                    if html:
                        return html
            output_type = str(value.get("output_type") or "").lower()
            if output_type == "html":
                for key in ("content", "html"):
                    html = _extract_html_from_tool_result(value.get(key), depth + 1)
                    if html:
                        return html
            for key in ("content", "html", "result"):
                html = _extract_html_from_tool_result(value.get(key), depth + 1)
                if html:
                    return html
            return None
        if isinstance(value, list):
            for item in value:
                html = _extract_html_from_tool_result(item, depth + 1)
                if html:
                    return html
            return None
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        if text[:1] in ("{", "["):
            try:
                parsed = json.loads(text)
            except Exception:
                pass
            else:
                return _extract_html_from_tool_result(parsed, depth + 1)
        return _extract_html_document(text)

    async def _auto_render_final_html(
        final_value: Any,
    ) -> tuple[List[str], Optional[str]]:
        """Render final HTML into a real html_interpreter step when missing."""
        auto_html = _extract_html_from_tool_result(final_value)
        sql_report_path = _select_existing_sql_backed_report_file(
            react_state.get("sql_backed_report_files", [])
        )
        if not auto_html and not sql_report_path:
            return [], None

        was_html_rendered = any(
            (s.get("action") or "").strip().lower() == "html_interpreter"
            or any(
                (o.get("output_type") or "").strip().lower() == "html"
                for o in s.get("outputs", [])
                if isinstance(o, dict)
            )
            for s in history_steps
        )
        if was_html_rendered:
            return [], None

        try:
            render_path = sql_report_path
            render_reason = (
                "code_interpreter 已基于已保存 SQL 结果生成报告文件，"
                "因此自动补充报告预览步骤"
            )
            render_thought = "自动渲染 SQL 查询结果驱动的 HTML 报告"
            if not render_path:
                safe_conv_id = re.sub(
                    r"[^A-Za-z0-9_.-]+",
                    "_",
                    cache_conv_id or "default",
                )[:48]
                render_path = os.path.join(
                    tempfile.gettempdir(),
                    f"auto_report_{safe_conv_id}_{uuid.uuid4().hex[:8]}.html",
                )
                with open(render_path, "w", encoding="utf-8") as f:
                    f.write(auto_html)
                render_reason = (
                    "最终回答包含HTML，但没有调用html_interpreter，"
                    "因此自动补充报告预览步骤"
                )
                render_thought = "自动将最终 HTML 渲染为可预览报告"

            render_result = await html_interpreter(
                file_path=render_path,
                title="运营报告",
            )
            render_payload = json.loads(render_result)
            render_chunks = [
                item
                for item in render_payload.get("chunks", [])
                if isinstance(item, dict)
            ]
            if not render_chunks:
                return [], None

            events: List[str] = []
            auto_step_id, auto_step_event = build_step(
                "html_interpreter",
                "Auto-render final HTML report",
                phase="生成报告",
            )
            events.append(auto_step_event)
            auto_history_step = {
                "id": auto_step_id,
                "title": "html_interpreter",
                "detail": "Auto-render final HTML report",
                "phase": "生成报告",
                "thought": render_thought,
                "action_intention": "生成HTML报告",
                "action_reason": render_reason,
                "action": "html_interpreter",
                "action_input": json.dumps(
                    {"file_path": render_path, "title": "运营报告"},
                    ensure_ascii=False,
                ),
                "outputs": [],
                "status": "running",
            }
            events.append(
                step_meta(
                    auto_step_id,
                    auto_history_step["thought"],
                    "html_interpreter",
                    auto_history_step["action_input"],
                    "html_interpreter",
                    action_intention=auto_history_step["action_intention"],
                    action_reason=auto_history_step["action_reason"],
                )
            )
            for item in render_chunks:
                output_type = item.get("output_type", "text")
                content = item.get("content")
                title = item.get("title")
                chunk_content = (
                    {"content": content, "title": title} if title else content
                )
                events.append(step_chunk(auto_step_id, output_type, chunk_content))
                auto_history_step["outputs"].append(
                    {"output_type": output_type, "content": chunk_content}
                )
            auto_history_step["status"] = "done"
            apply_step_timing(auto_step_id, auto_history_step)
            history_steps.append(auto_history_step)
            events.append(step_done(auto_step_id))
            return events, "HTML运营报告已生成，请在右侧预览或下载。"
        except Exception as e:
            logger.warning(f"Auto html_interpreter failed: {e}")
            return [], None

    def _collect_history_summary(steps: List[Dict[str, Any]]) -> str:
        """Build a summary from all completed history steps' observations."""
        parts: List[str] = []
        for s in steps:
            if s.get("status") != "done":
                continue
            action = s.get("action") or ""
            outputs = s.get("outputs") or []
            for out in outputs:
                content = out.get("content") or ""
                if not content:
                    continue
                if not isinstance(content, str):
                    continue
                # Skip raw SQL, code blocks, and very short outputs
                if _looks_like_raw_sql(content):
                    continue
                if out.get("output_type") == "code":
                    continue
                if len(content) < 20:
                    continue
                # Use thought/action_intention as label if available
                label = (
                    s.get("action_intention")
                    or s.get("thought")
                    or action
                    or "Step"
                )
                # Truncate long observations
                if len(content) > 500:
                    content = content[:500] + "..."
                parts.append(f"**{label}**:\n{content}")
        return "\n\n".join(parts) if parts else ""

    def should_advance_todo(
        action_name: Optional[str],
        thought: Optional[str] = None,
        observation_text: Optional[str] = None,
    ) -> bool:
        """Heuristically decide whether the current todo is actually complete."""
        if not _todo_list:
            return False

        active_idx = _active_todo_index()
        if active_idx is None:
            return False

        action_lower = _normalize_text(action_name)
        thought_lower = _normalize_text(thought)
        observation_lower = _normalize_text(observation_text)
        current_todo = _normalize_text(_todo_list[active_idx].get("content"))
        next_todo = (
            _normalize_text(_todo_list[active_idx + 1].get("content"))
            if active_idx + 1 < len(_todo_list)
            else ""
        )

        history = _todo_action_history.setdefault(active_idx, [])
        if action_lower:
            history.append(action_lower)

        transition_markers = [
            "next step",
            "now i need",
            "now i should",
            "now let me",
            "现在需要",
            "下一步",
            "接下来",
            "然后",
            "接着",
            "接下来我将",
        ]
        if next_todo and any(marker in thought_lower for marker in transition_markers):
            if any(token and token in thought_lower for token in next_todo.split()):
                return True

        if action_lower == "html_interpreter":
            return True

        if action_lower in {
            "load_skill",
            "execute_skill_script",
            "execute_skill_script_file",
        }:
            if next_todo and next_todo in thought_lower:
                return True
            if _is_report_like(next_todo) and _is_report_like(thought_lower):
                return True

        if action_lower == "sql_query":
            sql_calls = sum(1 for item in history if item == "sql_query")
            if sql_calls < 2:
                return False

            if next_todo and any(
                token and token in thought_lower for token in next_todo.split()
            ):
                return True

            if _is_report_like(next_todo) and (
                "summary" in thought_lower
                or "summarize" in thought_lower
                or "整理" in thought_lower
                or "汇总" in thought_lower
                or "报告" in thought_lower
                or "分析" in thought_lower
                or "建议" in thought_lower
            ):
                return True

            if current_todo and not _is_report_like(current_todo):
                completion_markers = [
                    "enough information",
                    "collected enough",
                    "gathered enough",
                    "completed metadata",
                    "obtained the overview",
                    "获取了足够",
                    "已经获取了足够",
                    "已完成",
                    "已获取",
                    "整理一下",
                    "数据已获取",
                    "查询完成",
                    "查询完毕",
                    "数据收集完成",
                    "可以生成",
                    "可以开始",
                ]
                if any(marker in thought_lower for marker in completion_markers):
                    return True

            # Safety net: force advance after too many SQL rounds
            if sql_calls >= 8:
                logger.warning(
                    f"sql_query stuck for {sql_calls} rounds, forcing advance"
                )
                return True

            return False

        if action_lower in {"code_interpreter", "execute_tool", "shell_interpreter"}:
            if _is_report_like(current_todo):
                return False
            if next_todo and any(
                token and token in thought_lower for token in next_todo.split()
            ):
                return True
            if observation_lower and _is_report_like(observation_lower):
                return True

        return False

    def advance_todo_list() -> Optional[List[Dict[str, str]]]:
        """Advance one todo when the current task appears substantively complete."""
        if not _todo_list:
            return None

        changed = False
        active_idx = _active_todo_index()

        if active_idx is not None:
            _todo_list[active_idx]["status"] = "completed"
            changed = True
            _todo_action_history.pop(active_idx, None)
            for next_item in _todo_list[active_idx + 1 :]:
                if next_item.get("status") == "pending":
                    next_item["status"] = "in_progress"
                    _todo_action_history.pop(active_idx + 1, None)
                    break
        else:
            for item in _todo_list:
                if item.get("status") == "pending":
                    item["status"] = "in_progress"
                    changed = True
                    break

        return list(_todo_list) if changed else None

    # Build a hint listing all images currently available in
    # STATIC_MESSAGE_IMG_PATH so the LLM can reference them correctly in
    # html_interpreter.
    # NOTE: This is the initial hint at prompt build time. Images generated
    # during the session are tracked in react_state["generated_images"] and
    # appended to html_interpreter output dynamically.
    available_images_hint = ""

    # Check if skill is pre-selected to use simplified prompt
    is_skill_mode = pre_matched_skill is not None
    _skill_name = pre_matched_skill.metadata.name if pre_matched_skill else "skill"

    if is_skill_mode:
        # Simplified prompt for skill mode - only skill-related tools +
        # html_interpreter
        workflow_prompt = f"""
你是中涣信息智能助手，负责执行用户选择的技能任务。
请始终使用与用户输入相同的语言回复。

## ⚠️ OUTPUT FORMAT (READ THIS FIRST - most errors happen here)
Every response MUST follow this EXACT format. Missing ANY field = error + wasted retry.

Thought: 你的分析（简短）
Action Intention: 这步做什么（<=18中文字）
Action Reason: 为什么做（<=30中文字）
Action: 工具名（如 sql_query, code_interpreter, html_interpreter, todowrite, terminate）
Action Input: JSON参数

**FORBIDDEN patterns that will cause errors:**
✗ "让我先想想..." (没有Action → 报错)
✗ "我们有了关键数据" (没有Action → 报错)  
✗ "正在生成分析代码" (没有Action → 报错)
✗ 输出英文思考 (必须用中文)
✗ 一次输出多个Action (如同时输出5个sql_query → 只有第1个会执行)
✗ 在Action之后继续写自然语言 (Observation由系统返回，不要自己写)

**CRITICAL: ONE action per response. NEVER output multiple Actions.**
After calling todowrite or sql_query, STOP. Wait for Observation. Do NOT add
more Actions in the same response.

**CORRECT pattern:**
Thought: 查询五月各线路营收
Action: sql_query
Action Input: {{"sql": "SELECT ..."}}
(然后等待系统返回Observation，再决定下一步)

## Autonomous Decision Principles
1. Strictly follow the instructions of the loaded skill.
2. For each step, output Thought -> Action Intention -> Action Reason -> Action
   -> Action Input.
3. Wait for the system to return Observation before deciding on the next step.
4. For follow-up requests such as "更详细点", "继续", "展开", or "补充",
   preserve the previous explicit filters from the conversation/history
   (date, company, department, line, vehicle, driver, metric scope) unless the
   user explicitly changes them. Do NOT replace a requested historical date
   with `ORDER BY target_date DESC LIMIT ...`.
5. **[Mandatory Rule] Report generation MUST follow this exact 3-step workflow:**
   Step 1: Call `sql_query` to get data (results auto-saved as `SQL_RESULT_n`).
   Step 2: Call `code_interpreter` to read saved SQL results with
           `get_only_sql_result()`, `get_sql_result('SQL_RESULT_n')`, or
           `find_sql_result_by_columns([...])`,
           compute ALL report metrics (totals, ratios, rates), and write HTML
           to `/tmp/report.html`.
   Step 3: Call `html_interpreter(file_path="/tmp/report.html")` to render.
   **NEVER generate HTML with hardcoded numbers. EVERY number and business
   conclusion in the report MUST be computed from saved SQL results inside
   `code_interpreter`, stored in `report_facts`, and rendered from
   `report_facts`.**
   Only use `template_path` mode if the skill explicitly provides HTML templates
   in its `templates/` directory and its documentation references them.
6. If the task does not require generating a report, directly call terminate to
return the final result. The Action Input format must be
{{"result": "final answer"}}.
7. **[Data Integrity - MANDATORY] Report generation workflow:**
   a) Call `sql_query` → results saved as `SQL_RESULT_1`, `SQL_RESULT_2`, etc.
   b) Call `code_interpreter` with this code pattern:
      ```python
      result = get_only_sql_result()
      # If multiple SQL results exist, use get_sql_result('SQL_RESULT_n')
      # or find_sql_result_by_columns([...]) to select the intended result.
      require_columns(result, ["total_value", "total_base"])
      rows = sql_result_rows(result)
      # Compute ALL metrics from required SQL columns — do NOT hardcode
      # numbers, guess result order like data[0], guess row indexes like row[15],
      # or silently default missing columns to 0.
      total_value = sum(to_float(require_value(row, "total_value")) for row in rows)
      total_base = sum(to_float(require_value(row, "total_base")) for row in rows)
      rate = round(total_value / total_base * 100, 2) if total_base else 0
      report_facts = {{
          "total_value": total_value,
          "total_base": total_base,
          "rate": rate,
          "scope_note": "HTML conclusions may only use these facts.",
      }}
      save_report_facts(report_facts)
      # Generate HTML using ONLY report_facts values. If a dimension was not
      # queried, write "本轮未查询，暂不判断" instead of inventing a conclusion.
      html = '<div>' + str(report_facts["rate"]) + '%</div>'
      write_sql_report_html('/tmp/report.html', html, report_facts)
      ```
      If HTML generation is split into a later `code_interpreter` call, the
      later call MUST start with `report_facts = load_report_facts()` before
      using any `report_facts[...]` value.
   c) Call `html_interpreter(file_path="/tmp/report.html")`.
   If a query returns empty data, explicitly state "暂无数据" for that metric.
   NEVER fabricate, estimate, or hallucinate any number.

{skill_prompt_context}
{execution_instruction}

## Skill Execution Norms
### Resource Usage
- **Need to execute skill script** -> Use `execute_skill_script_file` with
parameters {{"skill_name": "skill name", "script_file_name": "script file name",
"args": {{parameters}}}}. This tool will automatically handle image copying and
data recording.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.
- **Need to generate report** -> Call `html_interpreter`. **Default: directly pass
complete HTML via the `html` parameter** — you generate the full HTML code
yourself (including `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`, styles,
content). The HTML can be as long as needed. **Only use `template_path` if the
skill explicitly provides HTML templates in its `templates/` directory and its
documentation tells you to use them.** Do not use `code_interpreter` to generate
the report.

## Available Tools Description
1. **execute_skill_script_file** (recommended for executing skill scripts): Execute
script files in the skills scripts directory, automatically handling
post-processing such as copying images to the static directory and recording
calculation results.
   Parameters: {{"skill_name": "skill name", "script_file_name": "script file
name", "args": {{parameters}}}}
   - Example: {{"skill_name": "{_skill_name}",
"script_file_name": "calculate_ratios.py",
"args": {{"input_data": "..."}}}}
   - **Must use this tool when executing skill scripts**, do not use
shell_interpreter.
2. **get_skill_resource**: Read reference documents, configurations, templates, and
other non-script resource files in the skill.
   Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
   - Read reference document: {{"skill_name": "{_skill_name}",
"resource_path": "references/analysis_framework.md"}}
   - Note: For generating reports, prefer using html_interpreter directly with the
`html` parameter. Only use template_path if the skill explicitly provides
templates.
3. **execute_skill_script**: Execute the inline script defined in the skill
(backup). Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{"parameter name": "parameter value"}}}}
4. **shell_interpreter**: Execute shell/bash commands (only for non-skill script
system commands, such as ls, cat, etc.).
   Parameters: {{"code": "shell command"}}
   - Each call is independent and does not retain state. If multi-step operations
are needed, use `&&` or `;` to connect commands.
   - **Note: Do not use this tool to execute skill scripts**, as it will not
automatically handle images and data recording.
5. **html_interpreter**: Render HTML as an interactive web report. This is the ONLY
way to display reports on the right panel.
   **File mode (REQUIRED for data reports)**:
   {{"file_path": "/tmp/report.html", "title": "title"}}
   - MUST use file mode for reports with SQL data.
   - Write HTML to file with code_interpreter first (computing ALL numbers from
   SQL_QUERY_RESULTS), then pass file_path.
   - **IMPORTANT**: Always use `/tmp/` as the directory.
   **Inline mode** (ONLY for reports with NO numeric data):
   {{"html": "<html>...</html>", "title": "title"}}
   **Template mode**:
   {{"template_path": "skill/templates/xxx.html", "data": {{...}}, "title": "title"}}
   {available_images_hint}
6. **sql_query**: Execute a read-only SQL query against the selected database.
Parameters: {{"sql": "SELECT statement"}}
7. **todowrite**: Create and manage a structured task list. Use for complex tasks
(3+ steps) to plan and track progress. Pass the FULL list every time. Each item:
{{"content": "description", "status": "pending|in_progress|completed|cancelled",
"priority": "high|medium|low"}}. Only ONE task in_progress at a time.
IMPORTANT: You MUST call todowrite again after EACH task completes to update status.
The user sees progress in real time — never skip an update.
Parameters: {{"todos": [{{...}}]}}
8. **terminate**: Return the final answer when the task is completed. Action Input
must be {{"result": "your final answer content"}}.

## Task Management
For complex tasks that require 3 or more steps, use the `todowrite` tool to create
a structured task plan BEFORE starting work. This helps users track your progress.
- Call `todowrite` with the FULL todo list (all items) each time you update.
- Mark exactly ONE task as `in_progress` at a time.
- Mark tasks `completed` immediately after finishing each one.
- Do NOT use todowrite for simple single-step tasks.

CRITICAL: You MUST call `todowrite` to update the task list at EVERY transition:
1. BEFORE starting a task: mark it `in_progress` (call todowrite)
2. AFTER finishing a task: mark it `completed` AND mark the next one
   `in_progress` (call todowrite)
3. Never skip updating — the user sees this progress in real time.
Example flow for 3 tasks:
- Create plan: [task1=in_progress, task2=pending, task3=pending] → call todowrite
- Finish task1: [task1=completed, task2=in_progress, task3=pending] → call todowrite
- Finish task2: [task1=completed, task2=completed, task3=in_progress] → call todowrite
- Finish task3: [task1=completed, task2=completed, task3=completed] → call todowrite

{file_context}
{knowledge_context}
{database_context}

## Data Authenticity Guard
- Report metrics must come from successful `sql_query` or skill observations.
- If `sql_query` returns a saved `SQL_RESULT_n`, use the saved full result via
  helper functions (`get_only_sql_result()`, `get_sql_result('SQL_RESULT_n')`,
  or `find_sql_result_by_columns([...])`) for report generation; the markdown
  table is only a display preview.
- If a SQL query fails or returns insufficient data, fix the query or clearly
  state that the report cannot be completed; never invent KPI values.
- Before rendering an HTML report, verify that every core metric is traceable to
  a successful observation in this conversation.

## ReAct Output Format (STRICT - every response MUST follow this format)
You MUST output ALL of the following fields in order. Missing any field will
cause an error and waste a retry. Do NOT output natural language after Thought.

Thought: Analyze current task status and think about what to do next
Action Intention: What this step will do, plain text, MUST be concise and fit in
<= 18 Chinese chars or <= 8 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action Reason: Why this action is needed now, plain text, MUST be concise and fit in
<= 30 Chinese chars or <= 12 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action: The exact tool name, no backticks, no markdown (e.g. sql_query not `sql_query`)
Action Input: JSON parameters for the tool

**CRITICAL RULES:**
- NEVER output just Thought without Action + Action Input. All three are REQUIRED.
- NEVER continue reasoning in natural language after Thought. Go straight to Action.
- Action must be a bare tool name: sql_query, code_interpreter, html_interpreter,
  todowrite, terminate, etc. Do NOT wrap in backticks or quotes.
- Action Input must be valid JSON.

Example (correct):
Thought: 查询五月各线路营收排名
Action Intention: 查询线路营收TOP15
Action Reason: 为报告提供线路维度对比数据
Action: sql_query
Action Input:
{{"sql": "SELECT line_code FROM ads_ope_summary_line_d LIMIT 15"}}

Example (WRONG - will fail):
Thought: 我需要查询数据...让我先想想...
(缺少 Action 和 Action Input，系统会报错)

Do not wrap ReAct labels with Markdown. Output `Action:` and `Action Input:`
exactly as plain line prefixes, not `**Action:**`, headings, bullets, or code
fences.
""".strip()

        tool_pack = ToolPack(
            [
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                shell_interpreter,
                html_interpreter,
                sql_query,
                todowrite,
                Terminate(),
            ]
            + business_tools
        )
    else:
        # Full prompt with all tools when no skill is pre-selected
        workflow_prompt = f"""
你是中涣信息智能助手，能够根据用户任务自主选择工具解决问题。
请始终使用与用户输入相同的语言回复。

## ⚠️ OUTPUT FORMAT (READ THIS FIRST - most errors happen here)
Every response MUST follow this EXACT format. Missing ANY field = error + wasted retry.

Thought: 你的分析（简短）
Action Intention: 这步做什么（<=18中文字）
Action Reason: 为什么做（<=30中文字）
Action: 工具名（如 sql_query, code_interpreter, html_interpreter, todowrite, terminate）
Action Input: JSON参数

**FORBIDDEN patterns that will cause errors:**
✗ "让我先想想..." (没有Action → 报错)
✗ "我们有了关键数据" (没有Action → 报错)
✗ "正在生成分析代码" (没有Action → 报错)
✗ 输出英文思考 (必须用中文)
✗ 一次输出多个Action (如同时输出5个sql_query → 只有第1个会执行)
✗ 在Action之后继续写自然语言 (Observation由系统返回，不要自己写)

**CRITICAL: ONE action per response. NEVER output multiple Actions.**
After calling todowrite or sql_query, STOP. Wait for Observation. Do NOT add
more Actions in the same response.

**CORRECT pattern:**
Thought: 查询五月各线路营收
Action: sql_query
Action Input: {{"sql": "SELECT ..."}}
(然后等待系统返回Observation，再决定下一步)

## Autonomous Decision Principles
1. Carefully analyze the user's task requirements.
2. Autonomously select required tools based on requirements (do not follow a fixed
order, select as needed).
3. For each step, output Thought -> Action Intention -> Action Reason -> Action
   -> Action Input.
4. Wait for the system to return Observation before deciding on the next step.
5. For follow-up requests such as "更详细点", "继续", "展开", or "补充",
   preserve the previous explicit filters from the conversation/history
   (date, company, department, line, vehicle, driver, metric scope) unless the
   user explicitly changes them. Do NOT replace a requested historical date
   with `ORDER BY target_date DESC LIMIT ...`.
6. When the task is completed, call the terminate tool to return the final result.
The Action Input format must be {{"result": "final answer"}}.
7. **[Mandatory Rule] Report generation MUST follow this exact 3-step workflow:**
   Step 1: Call `sql_query` to get data (results auto-saved as `SQL_RESULT_n`).
   Step 2: Call `code_interpreter` to read saved SQL results with
           `get_only_sql_result()`, `get_sql_result('SQL_RESULT_n')`, or
           `find_sql_result_by_columns([...])`,
           compute ALL report metrics (totals, ratios, rates), and write HTML
           to `/tmp/report.html`.
   Step 3: Call `html_interpreter(file_path="/tmp/report.html")` to render.
   **NEVER generate HTML with hardcoded numbers. EVERY number and business
   conclusion in the report MUST be computed from saved SQL results inside
   `code_interpreter`, stored in `report_facts`, and rendered from
   `report_facts`.**
8. **[Data Integrity - MANDATORY] Report generation workflow:**
   a) Call `sql_query` → results saved as `SQL_RESULT_1`, `SQL_RESULT_2`, etc.
   b) Call `code_interpreter` with this code pattern:
      ```python
      result = get_only_sql_result()
      # If multiple SQL results exist, use get_sql_result('SQL_RESULT_n')
      # or find_sql_result_by_columns([...]) to select the intended result.
      require_columns(result, ["total_value", "total_base"])
      rows = sql_result_rows(result)
      # Compute ALL metrics from required SQL columns — do NOT hardcode
      # numbers, guess result order like data[0], guess row indexes like row[15],
      # or silently default missing columns to 0.
      total_value = sum(to_float(require_value(row, "total_value")) for row in rows)
      total_base = sum(to_float(require_value(row, "total_base")) for row in rows)
      rate = round(total_value / total_base * 100, 2) if total_base else 0
      report_facts = {{
          "total_value": total_value,
          "total_base": total_base,
          "rate": rate,
          "scope_note": "HTML conclusions may only use these facts.",
      }}
      save_report_facts(report_facts)
      # Generate HTML using ONLY report_facts values. If a dimension was not
      # queried, write "本轮未查询，暂不判断" instead of inventing a conclusion.
      html = '<div>' + str(report_facts["rate"]) + '%</div>'
      write_sql_report_html('/tmp/report.html', html, report_facts)
      ```
      If HTML generation is split into a later `code_interpreter` call, the
      later call MUST start with `report_facts = load_report_facts()` before
      using any `report_facts[...]` value.
   c) Call `html_interpreter(file_path="/tmp/report.html")`.
   If a query returns empty data, explicitly state "暂无数据" for that metric.
   NEVER fabricate, estimate, or hallucinate any number.

## Task Management
For complex tasks that require 3 or more steps, use the `todowrite` tool to create
a structured task plan BEFORE starting work. This helps users track your progress.
- Call `todowrite` with the FULL todo list (all items) each time you update.
- Mark exactly ONE task as `in_progress` at a time.
- Mark tasks `completed` immediately after finishing each one.
- Do NOT use todowrite for simple single-step tasks.

CRITICAL: You MUST call `todowrite` to update the task list at EVERY transition:
1. BEFORE starting a task: mark it `in_progress` (call todowrite)
2. AFTER finishing a task: mark it `completed` AND mark the next one
   `in_progress` (call todowrite)
3. Never skip updating — the user sees this progress in real time.
Example flow for 3 tasks:
- Create plan: [task1=in_progress, task2=pending, task3=pending] → call todowrite
- Finish task1: [task1=completed, task2=in_progress, task3=pending] → call todowrite
- Finish task2: [task1=completed, task2=completed, task3=in_progress] → call todowrite
- Finish task3: [task1=completed, task2=completed, task3=completed] → call todowrite

## Available Skills List (Pre-loaded)
{skills_context}

## Skill Execution Norms (Important)
When using a skill, the following rules must be followed:

### 1. Understand the Workflow
After loading the skill, carefully read the **Core Workflow** section in SKILL.md
and execute it in order. If a step explicitly states conditions to skip (such as
when user intent is clear), directly skip to the next step; do not force the
execution of every step. Prioritize producing results quickly, and perform
iterative optimization in subsequent steps.

### 2. Resource Usage Timing
- **Need to calculate/process data** -> Use `execute_skill_script_file` to execute
scripts in the skill's scripts directory (this tool automatically handles images
and data recording). Parameters are {{"skill_name": "skill name",
"script_file_name": "script.py", "args": {{parameters}}}}.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.

### 3. Execution Order
Complete each workflow step before moving to the next. Do not mix multiple tool
calls in the same step.

### 4. Special Scenarios
- For report generation: Same as the principle above, must finally call
`html_interpreter` to render. Prefer file mode for long HTML.

## Available Tools Description
1. **load_skill**: Load skill content by skill name and file path.
Parameters: {{"skill_name": "skill name", "file_path": "skill file path"}}
2. **execute_skill_script_file**: Execute script files in the skill's scripts
directory. Parameters: {{"skill_name": "skill name",
"script_file_name": "script file name", "args": {{parameters}}}}
3. **get_skill_resource**: Read reference documents in the skill.
Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
4. **execute_skill_script**: Execute the inline script defined in the skill.
Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{parameters}}}}
5. **shell_interpreter**: Execute shell/bash commands.
Parameters: {{"code": "shell command"}}
6. **code_interpreter**: Execute arbitrary Python code.
Parameters: {{"code": "python code string"}}
7. **load_file**: Load uploaded file info. Parameters: none.
8. **execute_analysis**: Execute quick analysis on uploaded Excel/CSV file.
Parameters: none.
9. **knowledge_retrieve**: Retrieve relevant info from knowledge base.
Parameters: {{"query": "search query"}}
10. **sql_query**: Execute a read-only SQL query against the selected database.
Parameters: {{"sql": "SELECT statement"}}
11. **load_tools**: Resolve required tools for the selected skill. Parameters: none.
12. **execute_tool**: Execute a tool by name with JSON args.
Parameters: {{"tool_name": "tool name", "args": {{parameters}}}}
13. **html_interpreter**: Render HTML as an interactive web report (the ONLY way
to display reports on the right panel).
   File mode (recommended):
   {{"file_path": "/tmp/report.html", "title": "title"}}
   - **IMPORTANT**: When writing HTML with code_interpreter, always use `/tmp/` as
   the directory (e.g. `/tmp/report.html`). Other directories may not exist.
   If you must use another path, create the directory first with
   `import os; os.makedirs('/path/to/dir', exist_ok=True)`.
   Inline mode: {{"html": "<html>...</html>", "title": "title"}}
   Template mode:
   {{"template_path": "skill/templates/xxx.html", "data": {{...}}, "title": "title"}}
14. **todowrite**: Create and manage a structured task list. Use for complex tasks
(3+ steps) to plan and track progress. Pass the FULL list every time. Each item:
{{"content": "description", "status": "pending|in_progress|completed|cancelled",
"priority": "high|medium|low"}}. Only ONE task in_progress at a time.
IMPORTANT: You MUST call todowrite again after EACH task completes to update status.
The user sees progress in real time — never skip an update.
Parameters: {{"todos": [{{...}}]}}
15. **terminate**: Finish the task. Parameters: {{"result": "final answer"}}

{file_context}
{knowledge_context}
{database_context}

## Data Authenticity Guard
- Report metrics must come from successful `sql_query` or tool observations.
- If `sql_query` returns a saved `SQL_RESULT_n`, use the saved full result via
  helper functions (`get_only_sql_result()`, `get_sql_result('SQL_RESULT_n')`,
  or `find_sql_result_by_columns([...])`) for report generation; the markdown
  table is only a display preview.
- If a SQL query fails or returns insufficient data, fix the query or clearly
  state that the report cannot be completed; never invent KPI values.
- Before rendering an HTML report, verify that every core metric is traceable to
  a successful observation in this conversation.

## ReAct Output Format (STRICT - every response MUST follow this format)
You MUST output ALL of the following fields in order. Missing any field will
cause an error and waste a retry. Do NOT output natural language after Thought.

Thought: Analyze current task status and think about what to do next
Action Intention: What this step will do, plain text, MUST be concise and fit in
<= 18 Chinese chars or <= 8 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action Reason: Why this action is needed now, plain text, MUST be concise and fit in
<= 30 Chinese chars or <= 12 English words. If too long, rewrite shorter.
Do not use ellipsis.
Action: The exact tool name, no backticks, no markdown (e.g. sql_query not `sql_query`)
Action Input: JSON parameters for the tool

**CRITICAL RULES:**
- NEVER output just Thought without Action + Action Input. All three are REQUIRED.
- NEVER continue reasoning in natural language after Thought. Go straight to Action.
- Action must be a bare tool name: sql_query, code_interpreter, html_interpreter,
  todowrite, terminate, load_skill, etc. Do NOT wrap in backticks or quotes.
- Action Input must be valid JSON.

Example (correct):
Thought: 查询五月各线路营收排名
Action Intention: 查询线路营收TOP15
Action Reason: 为报告提供线路维度对比数据
Action: sql_query
Action Input:
{{"sql": "SELECT line_code FROM bigdata_ticket_revenue LIMIT 15"}}

Example (WRONG - will fail):
Thought: 我需要查询数据...让我先想想...
(缺少 Action 和 Action Input，系统会报错)

Do not wrap ReAct labels with Markdown. Output `Action:` and `Action Input:`
exactly as plain line prefixes, not `**Action:**`, headings, bullets, or code
fences.
""".strip()

        tool_pack = ToolPack(
            [
                load_skill,
                load_tools,
                knowledge_retrieve,
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                code_interpreter,
                shell_interpreter,
                html_interpreter,
                sql_query,
                todowrite,
                Terminate(),
            ]
            + business_tools
        )

    # Debug: print all registered tools
    logger.info(f"ToolPack resources: {list(tool_pack._resources.keys())}")
    if "execute_skill_script" not in tool_pack._resources:
        logger.error("execute_skill_script NOT in ToolPack!")

    # Combine tool_pack and knowledge_resources into a single ResourcePack
    all_resources = [tool_pack]
    if knowledge_resources:
        all_resources.extend(knowledge_resources)
    # Convert workflow_prompt to PromptTemplate so it is used as system prompt
    # Use jinja2 format to avoid issues with JSON braces { } in the prompt
    workflow_prompt_template = PromptTemplate(
        template=workflow_prompt,
        input_variables=[],
        template_format="jinja2",
    )

    agent_builder = (
        ReActAgent(max_retry_count=50)
        .bind(context)
        .bind(agent_memory)
        .bind(llm_config)
        .bind(tool_pack)
        .bind(workflow_prompt_template)
    )

    agent = await agent_builder.build()

    parser = ReActOutputParser()
    received = AgentMessage(content=user_input)
    stream_queue: asyncio.Queue = asyncio.Queue()

    # Wire up context-management status events into the SSE stream.
    async def _context_status_callback(status: Dict[str, Any]) -> None:
        await stream_queue.put({"type": "context.status", **status})

    agent.init_context_management(
        config=await _load_context_budget_config(
            llm_client=llm_client,
            model_name=dialogue.model_name,
        ),
        model_name=dialogue.model_name,
        on_status_event=_context_status_callback,
    )

    async def stream_callback(event_type: str, payload: Dict[str, Any]) -> None:
        await stream_queue.put({"type": event_type, **payload})

    async def run_agent():
        return await agent.generate_reply(
            received_message=received,
            sender=agent,
            stream_callback=stream_callback,
        )

    agent_task = asyncio.create_task(run_agent())
    round_step_map: Dict[int, str] = {}
    pending_thoughts: Dict[
        int, List[str]
    ] = {}  # Buffer thinking content for delayed step creation
    pending_action_intentions: Dict[int, str] = {}
    pending_action_reasons: Dict[int, str] = {}
    # --- History persistence: collect step data during streaming ---
    history_steps: List[Dict[str, Any]] = []
    current_history_step: Optional[Dict[str, Any]] = None

    # Emit pre-loaded skill as an SSE step before agent starts processing
    if pre_matched_skill:
        skill_step_id, skill_step_event = build_step(
            f"Load Skill: {pre_matched_skill.metadata.name}",
            "Pre-loaded skill from user selection",
            phase="加载技能",
        )
        current_history_step = {
            "id": skill_step_id,
            "title": f"Load Skill: {pre_matched_skill.metadata.name}",
            "detail": "Pre-loaded skill from user selection",
            "phase": "加载技能",
            "thought": None,
            "action": None,
            "action_input": None,
            "outputs": [],
            "status": "done",
        }
        yield skill_step_event
        # Emit skill metadata as text chunk
        skill_desc = (
            f"Skill: {pre_matched_skill.metadata.name}"
            f" - {pre_matched_skill.metadata.description}"
        )
        yield step_chunk(skill_step_id, "text", skill_desc)
        current_history_step["outputs"].append(
            {"output_type": "text", "content": skill_desc}
        )
        # Emit skill instructions as markdown content (shows in right panel)
        if pre_matched_skill.instructions:
            yield step_chunk(skill_step_id, "markdown", pre_matched_skill.instructions)
            current_history_step["outputs"].append(
                {
                    "output_type": "markdown",
                    "content": pre_matched_skill.instructions,
                }
            )
        apply_step_timing(skill_step_id, current_history_step)
        yield step_done(skill_step_id)
        history_steps.append(current_history_step)
        current_history_step = None

    while True:
        if agent_task.done() and stream_queue.empty():
            break
        try:
            event = await asyncio.wait_for(stream_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        event_type = event.get("type")
        if event_type == "context.status":
            # Forward context-management status to frontend as-is.
            yield _sse_event(event)
        elif event_type == "thinking":
            # Parse thinking content but don't create step yet
            # Step will be created when 'act' event arrives with confirmed
            # action
            round_num = int(event.get("round") or (len(round_step_map) + 1))
            now = time.monotonic()
            round_thinking_started_at.setdefault(round_num, now)
            round_thinking_finished_at[round_num] = now
            llm_reply = event.get("llm_reply") or ""
            thought = None
            action_intention = None
            action_reason = None
            action = None
            action_input = None
            try:
                steps = parser.parse(llm_reply)
                if steps:
                    thought = steps[0].thought
                    action_intention = steps[0].action_intention
                    action_reason = steps[0].action_reason
                    action = steps[0].action
                    action_input = steps[0].action_input
            except Exception:
                pass

            # Store parsed thinking info in pending_thoughts for later use
            if round_num not in pending_thoughts:
                pending_thoughts[round_num] = []
            if thought:
                pending_thoughts[round_num].append(thought)
            intention_text = normalize_display_text(action_intention)
            if intention_text:
                pending_action_intentions[round_num] = intention_text
            reason_text = normalize_display_text(action_reason)
            if reason_text:
                pending_action_reasons[round_num] = reason_text
            # Don't emit anything yet - wait for 'act' event to create step

        elif event_type == "thinking_chunk":
            round_num = int(event.get("round") or (len(round_step_map) + 1))
            round_thinking_started_at.setdefault(round_num, time.monotonic())
            delta_thinking = event.get("delta_thinking") or ""
            delta_text = event.get("delta_text") or ""

            chunk = delta_thinking or delta_text
            if chunk:
                # Clean chunk: remove Action Input JSON to keep thought pure
                # Split on Action Input pattern and keep only thought part
                clean_chunk = re.split(
                    r"\n\s*Action\s*Input\s*:\s*\{", chunk, maxsplit=1
                )[0]
                # Also remove Action: lines
                clean_chunk = re.sub(r"\n\s*Action\s*:\s*\w+", "", clean_chunk)
                # Remove Thought: prefix if present
                if clean_chunk.startswith("Thought:"):
                    clean_chunk = clean_chunk[len("Thought:") :].strip()
                if clean_chunk:
                    if round_num not in pending_thoughts:
                        pending_thoughts[round_num] = []
                    pending_thoughts[round_num].append(clean_chunk)
                    if round_num not in round_step_map:
                        pending_step_id, pending_step_event = build_step(
                            "思考中",
                            "Thought/Action/Observation",
                        )
                        round_step_map[round_num] = pending_step_id
                        yield pending_step_event
                    # Stream thought chunk to frontend for real-time display
                    yield _sse_event({
                        "type": "step.thought",
                        "id": round_step_map[round_num],
                        "content": clean_chunk,
                    })

        elif event_type == "act":
            # Create step ONLY when action is confirmed
            round_num = int(event.get("round") or (len(round_step_map) + 1))

            action_output = event.get("action_output") or {}
            thoughts = action_output.get("thoughts")
            action = action_output.get("action")
            action_input = action_output.get("action_input")
            action_input_data = None
            if action_input is not None:
                if isinstance(action_input, str):
                    try:
                        action_input_data = json.loads(action_input)
                    except Exception:
                        action_input_data = action_input
                else:
                    action_input_data = action_input

            # Skip step display for terminate action — its output will be
            # sent as a streaming "final" event instead of a step card.
            # Also skip emitting the thought for terminate since it's noise.
            # Note: TerminateAction.run() sets terminate=True but does NOT
            # set the action field, so we must check the terminate boolean.
            is_terminate = action_output.get("terminate") or (
                action and action.lower() == "terminate"
            )
            if is_terminate:
                pending_thoughts.pop(round_num, [])
                pending_action_intentions.pop(round_num, None)
                pending_action_reasons.pop(round_num, None)
                # ── Auto-complete all remaining todos on terminate ──
                if _todo_list:
                    for t in _todo_list:
                        if t["status"] in ("pending", "in_progress"):
                            t["status"] = "completed"
                    yield _sse_event({"type": "plan.update", "tasks": list(_todo_list)})
                continue

            # ── TodoWrite: emit plan.update SSE and show step card ──
            if action and action.lower() == "todowrite":
                pending_thoughts.pop(round_num, [])
                pending_action_intentions.pop(round_num, None)
                pending_action_reasons.pop(round_num, None)
                # Extract todos from observation JSON
                obs_text = action_output.get("observations") or action_output.get(
                    "content"
                )
                todos_payload: List[Dict[str, str]] = []
                if obs_text:
                    try:
                        obs_json = (
                            json.loads(obs_text)
                            if isinstance(obs_text, str)
                            else obs_text
                        )
                        if isinstance(obs_json, dict):
                            todos_payload = obs_json.get("__todos__", [])
                    except Exception:
                        pass
                # Fallback: read from the closure variable
                if not todos_payload and _todo_list:
                    todos_payload = list(_todo_list)

                _td_total = len(todos_payload)
                _td_done = sum(
                    1 for t in todos_payload if t.get("status") == "completed"
                )
                if _td_done == 0:
                    todo_state = "init"
                elif _td_done == _td_total and _td_total > 0:
                    todo_state = "done"
                else:
                    todo_state = "progress"

                todo_meta = {
                    "state": todo_state,
                    "done": _td_done,
                    "total": _td_total,
                }
                _todo_step_title = (
                    f"TODO::{todo_state}:{_td_done}/{_td_total}"
                    if _td_total > 0
                    else f"TODO::{todo_state}"
                )

                # Emit or update the step card for this round
                # NOTE: Do NOT set phase — let it fall into the default
                # "Execution Steps" group so todowrite cards appear inline
                # alongside other action steps in chronological order.
                if round_num in round_step_map:
                    todo_step_id = round_step_map[round_num]
                    yield _sse_event(
                        {
                            "type": "step.start",
                            "step": step,
                            "id": todo_step_id,
                            "title": _todo_step_title,
                            "detail": "todowrite",
                            "todo_meta": todo_meta,
                        }
                    )
                else:
                    todo_step_id, todo_step_event = build_step(
                        _todo_step_title,
                        "todowrite",
                    )
                    round_step_map[round_num] = todo_step_id
                    yield _sse_event(
                        {
                            "type": "step.start",
                            "step": step,
                            "id": todo_step_id,
                            "title": _todo_step_title,
                            "detail": "todowrite",
                            "todo_meta": todo_meta,
                        }
                    )

                yield _sse_event({"type": "plan.update", "tasks": todos_payload})
                yield step_meta(
                    round_step_map[round_num],
                    None,
                    action,
                    None,
                    _todo_step_title,
                    todo_meta=todo_meta,
                )
                todo_step_id = round_step_map[round_num]
                todo_history_step = {
                    "id": todo_step_id,
                    "title": _todo_step_title,
                    "detail": "todowrite",
                    "thought": None,
                    "action_intention": None,
                    "action_reason": None,
                    "action": action,
                    "action_input": None,
                    "outputs": [],
                    "status": "done",
                    "todo_meta": todo_meta,
                }
                apply_step_timing(todo_step_id, todo_history_step, round_num=round_num)
                history_steps.append(todo_history_step)
                yield step_done(todo_step_id, round_num=round_num)
                continue

            # Collect buffered thoughts for history persistence
            # (already streamed to frontend via thinking_chunk handler)
            buffered_thoughts = pending_thoughts.pop(round_num, [])
            thought_text = None
            if buffered_thoughts:
                full_thought = "".join(buffered_thoughts)
                full_thought = re.split(r"\n\s*Action\s*:", full_thought, maxsplit=1)[
                    0
                ].strip()
                if full_thought.startswith("Thought:"):
                    full_thought = full_thought[len("Thought:") :].strip()
                if full_thought:
                    thought_text = full_thought
            action_intention = normalize_display_text(
                action_output.get("action_intention")
                or pending_action_intentions.pop(round_num, None)
                or action_output.get("phase")
            )
            action_reason = normalize_display_text(
                action_output.get("action_reason")
                or pending_action_reasons.pop(round_num, None)
            )
            display_thought = action_intention or summarize_thought(
                thought_text or thoughts, action
            )

            # Use the actual action name as the step title (Manus-style UI)
            action_title = action or f"ReAct Round {round_num}"
            if round_num in round_step_map:
                # Step already exists (from thinking) - update title with same id
                react_step_id = round_step_map[round_num]
                updated_event = _sse_event(
                    {
                        "type": "step.start",
                        "step": step,
                        "id": react_step_id,
                        "title": action_title,
                        "detail": "Thought/Action/Observation",
                    }
                )
                yield updated_event
            else:
                react_step_id, react_step_event = build_step(
                    action_title,
                    "Thought/Action/Observation",
                )
                round_step_map[round_num] = react_step_id
                yield react_step_event

            # --- History: create step record ---
            action_input_str = None
            if action_input is not None:
                action_input_str = (
                    action_input
                    if isinstance(action_input, str)
                    else json.dumps(action_input, ensure_ascii=False)
                )
            current_history_step = {
                "id": react_step_id,
                "title": action_title,
                "detail": "Thought/Action/Observation",
                "thought": display_thought,
                "action_intention": action_intention,
                "action_reason": action_reason,
                "action": action,
                "action_input": action_input_str,
                "outputs": [],
                "status": "running",
            }

            # Stream action code to frontend for right panel
            # (code_interpreter)
            code_payload = None
            if action == "code_interpreter" and isinstance(action_input_data, dict):
                code_payload = action_input_data.get("code")
            if isinstance(code_payload, str) and code_payload.strip():
                yield step_chunk(react_step_id, "code", code_payload)
                if current_history_step is not None:
                    current_history_step["outputs"].append(
                        {"output_type": "code", "content": code_payload}
                    )

            # Emit thinking metadata
            if thoughts or action or action_input:
                step_action_input = (
                    None if action == "code_interpreter" else action_input
                )
                yield step_meta(
                    react_step_id,
                    display_thought,
                    action,
                    step_action_input,
                    action_title,
                    action_intention=action_intention,
                    action_reason=action_reason,
                )

            # Emit observation (action execution result)
            observation_text = action_output.get("observations") or action_output.get(
                "content"
            )
            if observation_text:
                raw_chunks = emit_tool_chunks(react_step_id, observation_text)
                if raw_chunks:
                    for chunk in raw_chunks:
                        yield chunk
                else:
                    for chunk in chunk_text(str(observation_text), max_len=600):
                        yield step_chunk(react_step_id, "text", chunk)
                # --- History: collect outputs from observation ---
                if current_history_step is not None:
                    parsed_obs = None
                    if isinstance(observation_text, str):
                        try:
                            parsed_obs = json.loads(observation_text)
                        except Exception:
                            pass
                    if isinstance(parsed_obs, dict) and isinstance(
                        parsed_obs.get("chunks"), list
                    ):
                        for item in parsed_obs["chunks"]:
                            if isinstance(item, dict):
                                current_history_step["outputs"].append(
                                    {
                                        "output_type": item.get("output_type", "text"),
                                        "content": item.get("content"),
                                    }
                                )
                    elif isinstance(observation_text, str) and observation_text:
                        current_history_step["outputs"].append(
                            {
                                "output_type": "text",
                                "content": observation_text,
                            }
                        )

            # Mark step as done and track as last completed
            status = "done" if action_output.get("is_exe_success", True) else "failed"
            yield step_done(react_step_id, status, round_num=round_num)
            if (
                status == "done"
                and action
                and action.lower() != "todowrite"
                and should_advance_todo(
                    action, thought_text or thoughts, observation_text
                )
            ):
                updated_todos = advance_todo_list()
                if updated_todos:
                    yield _sse_event({"type": "plan.update", "tasks": updated_todos})
            # --- History: finalize step ---
            if current_history_step is not None:
                current_history_step["status"] = status
                apply_step_timing(
                    react_step_id,
                    current_history_step,
                    round_num=round_num,
                )
                history_steps.append(current_history_step)
                current_history_step = None

    try:
        reply = await agent_task
    except Exception as e:
        err_msg = f"React agent failed: {e}"
        error_payload = json.dumps(
            {
                "version": 1,
                "type": "react-agent",
                "final_content": err_msg,
                "steps": [
                    _sanitize_customer_facing_step(step) for step in history_steps
                ],
                "task_plan": list(_todo_list),
                "generated_images": react_state.get("generated_images", []),
            },
            ensure_ascii=False,
        )
        storage_conv.add_view_message(error_payload)
        storage_conv.end_current_round()
        storage_conv.save_to_storage()
        yield _sse_event({"type": "final", "content": err_msg})
        yield _sse_event({"type": "done"})
        return

    if reply.action_report and reply.action_report.terminate:
        raw_content = reply.action_report.content or ""
        final_content = raw_content
        try:
            steps = parser.parse(raw_content)
            if steps:
                action_input = steps[0].action_input
                if action_input:
                    if isinstance(action_input, str):
                        parsed_input = json.loads(action_input)
                    else:
                        parsed_input = action_input
                    if isinstance(parsed_input, dict) and "result" in parsed_input:
                        final_content = parsed_input["result"]
        except Exception:
            pass
        # Fallback: extract "result" value via regex if parsing failed
        if final_content == raw_content:
            m = re.search(
                r'"result"\s*:\s*"((?:[^"\\]|\\.)*)"',
                final_content,
                re.DOTALL,
            )
            if m:
                final_content = m.group(1).replace('\\"', '"').replace('\\n', '\n')

        auto_events, rendered_final_content = await _auto_render_final_html(
            final_content
        )
        for event in auto_events:
            yield event
        if rendered_final_content:
            final_content = rendered_final_content
    elif reply.action_report:
        # Loop ended without terminate (max retries or timeout).
        # reply.content is raw LLM output containing ReAct prefixes.
        # Try to extract a clean summary from the last step's thought.
        raw = reply.content or reply.action_report.content or ""
        final_content = raw
        try:
            steps = parser.parse(raw)
            if steps:
                last_step = steps[-1]
                # Prefer observation (execution result) > thought
                if last_step.observations:
                    final_content = last_step.observations
                elif last_step.thoughts:
                    final_content = last_step.thoughts
        except Exception:
            pass
        # Fallback: strip remaining ReAct prefixes via regex
        final_content = re.sub(
            r"^(Thought|Action|Action Input|Observation|Phase):\s*",
            "",
            final_content,
            flags=re.MULTILINE,
        ).strip()

        # If final_content looks like raw SQL or is very short, try to
        # build a richer summary from all completed history steps.
        if not final_content or _looks_like_raw_sql(final_content):
            collected = _collect_history_summary(history_steps)
            if collected:
                final_content = collected

        if not final_content:
            incomplete_hint = ""
            if _todo_list:
                pending = [
                    t["content"]
                    for t in _todo_list
                    if t.get("status") in ("pending", "in_progress")
                ]
                if pending:
                    incomplete_hint = (
                        " 未完成的步骤：" + "、".join(pending) + "。"
                        "请尝试用更简洁的指令继续完成。"
                    )
            final_content = (
                "任务执行已达到最大步数限制，请查看上方各步骤的执行结果。"
                + incomplete_hint
            )

        auto_events, rendered_final_content = await _auto_render_final_html(
            final_content
        )
        for event in auto_events:
            yield event
        if rendered_final_content:
            final_content = rendered_final_content
    else:
        final_content = reply.content or ""

    auto_events, rendered_final_content = await _auto_render_final_html(final_content)
    for event in auto_events:
        yield event
    if rendered_final_content:
        final_content = rendered_final_content
    final_content = _sanitize_customer_facing_answer(final_content)
    customer_history_steps = [
        _sanitize_customer_facing_step(step) for step in history_steps
    ]

    # Persist AI reply with structured history payload
    history_payload = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": final_content,
            "steps": customer_history_steps,
            "task_plan": list(_todo_list),
            "generated_images": react_state.get("generated_images", []),
        },
        ensure_ascii=False,
    )
    storage_conv.add_view_message(history_payload)
    storage_conv.end_current_round()
    storage_conv.save_to_storage()

    yield _sse_event({"type": "final", "content": final_content})
    yield _sse_event({"type": "done"})


async def _react_agent_stream(
    dialogue: ConversationVo,
) -> AsyncGenerator[str, None]:
    conv_id = dialogue.conv_uid or str(uuid.uuid4())
    database_name = None
    if dialogue.ext_info and isinstance(dialogue.ext_info, dict):
        database_name = dialogue.ext_info.get("database_name")
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        user_input = str(user_input or "")
    direct_reply = _get_direct_customer_facing_reply(database_name, user_input)
    if direct_reply is not None:
        from dbgpt.core import StorageConversation
        from dbgpt_serve.conversation.serve import Serve as ConversationServe

        final_content = _sanitize_customer_facing_answer(direct_reply)
        conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
        storage_conv = StorageConversation(
            conv_uid=conv_id,
            chat_mode=dialogue.chat_mode or "chat_react_agent",
            user_name=dialogue.user_name,
            sys_code=dialogue.sys_code,
            summary=dialogue.user_input,
            app_code=dialogue.app_code,
            conv_storage=conv_serve.conv_storage,
            message_storage=conv_serve.message_storage,
        )
        storage_conv.save_to_storage()
        storage_conv.start_new_round()
        storage_conv.add_user_message(user_input)
        history_payload = json.dumps(
            {
                "version": 1,
                "type": "react-agent",
                "final_content": final_content,
                "steps": [],
                "task_plan": [],
                "generated_images": [],
            },
            ensure_ascii=False,
        )
        storage_conv.add_view_message(history_payload)
        storage_conv.end_current_round()
        storage_conv.save_to_storage()
        yield _sse_event({"type": "final", "content": final_content})
        yield _sse_event({"type": "done"})
        return

    REACT_AGENT_MEMORY_CACHE.acquire(conv_id)
    try:
        async for event in _react_agent_stream_impl(dialogue, cache_conv_id=conv_id):
            yield event
    finally:
        REACT_AGENT_MEMORY_CACHE.release(conv_id)


# ---------------------------------------------------------------------------
# Share link APIs
# ---------------------------------------------------------------------------


class ShareCreateRequest(_BaseModel):
    """Request body for creating a share link."""

    conv_uid: str


class ShareCreateResponse(_BaseModel):
    """Response body for share link creation."""

    token: str
    conv_uid: str
    share_url: str


class ShareConvResponse(_BaseModel):
    """Public payload returned when viewing a shared conversation."""

    conv_uid: str
    token: str
    messages: list  # list[{role, context, order}]


def _get_share_dao():
    """Lazily instantiate the ShareLinkDao (avoids import-time side-effects)."""
    from dbgpt_app.share.models import ShareLinkDao

    return ShareLinkDao()


def _get_conversation_service():
    """Return the ConversationServe Service component."""
    from dbgpt_serve.conversation.config import SERVE_SERVICE_COMPONENT_NAME
    from dbgpt_serve.conversation.service.service import Service

    return CFG.SYSTEM_APP.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


@router.post("/v1/chat/share", response_model=Result)
async def create_share_link(
    body: ShareCreateRequest = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Create (or return existing) share link for a conversation.

    The returned ``share_url`` is a relative path that the client should
    prepend with the current host to form an absolute URL.
    """
    dao = _get_share_dao()
    created_by = user_token.user_id if user_token else None
    entity = dao.create_share(conv_uid=body.conv_uid, created_by=created_by)
    if entity is None:
        return Result.failed(msg="Failed to create share link")
    return Result.succ(
        ShareCreateResponse(
            token=entity.token,
            conv_uid=entity.conv_uid,
            share_url=f"/share/{entity.token}",
        )
    )


@router.get("/v1/chat/share/{token}", response_model=Result)
async def get_share_conversation(token: str):
    """Public endpoint — no authentication required.

    Returns the full conversation history for the given share token so that the
    replay page can reconstruct and animate the session.
    """
    dao = _get_share_dao()
    link = dao.get_by_token(token)
    if link is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")

    service = _get_conversation_service()
    from dbgpt_serve.conversation.api.schemas import ServeRequest

    history = service.get_history_messages(ServeRequest(conv_uid=link.conv_uid))

    messages = [
        {"role": m.role, "context": m.context, "order": m.order}
        for m in (history or [])
    ]
    return Result.succ(
        ShareConvResponse(
            conv_uid=link.conv_uid,
            token=token,
            messages=messages,
        )
    )


@router.delete("/v1/chat/share/{token}", response_model=Result)
async def delete_share_link(
    token: str,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Revoke a share link.  Only the owner (or any authenticated user) may delete."""
    dao = _get_share_dao()
    deleted = dao.delete_by_token(token)
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")
    return Result.succ({"deleted": True, "token": token})


@router.get("/v1/agent/files/download")
async def download_agent_file(
    file_path: str = Query(..., description="Absolute path to the file to download"),
):
    """Download a file created by agent tools (shell_interpreter, code_interpreter).

    Only files under allowed directories (/tmp, PILOT_PATH/tmp/) can be downloaded.
    This prevents arbitrary file access on the server.
    """
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from dbgpt.configs.model_config import PILOT_PATH, ROOT_PATH

    # If path is not absolute, resolve relative to ROOT_PATH (sandbox working dir)
    if not os.path.isabs(file_path):
        file_path = os.path.join(ROOT_PATH, file_path)

    # Resolve to absolute path and prevent path traversal
    try:
        resolved = os.path.realpath(file_path)
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Allowed base directories for agent-created files
    allowed_dirs = [
        os.path.realpath("/tmp"),
        os.path.realpath(os.path.join(PILOT_PATH, "tmp")),
        os.path.realpath(ROOT_PATH),
    ]

    if not any(resolved.startswith(d + os.sep) or resolved == d for d in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail="Access denied: file is not in an allowed directory",
        )

    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(resolved)
    return FileResponse(
        path=resolved,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/v1/agent/skills/download")
async def download_skill_package(
    skill_name: str = Query(..., description="Skill folder name"),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Download a skill folder as a .zip archive."""
    from fastapi import HTTPException

    if not skill_name:
        raise HTTPException(status_code=400, detail="skill_name is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    skill_path = (skills_dir / skill_name).resolve()

    # Security: ensure path is under skills_dir
    try:
        skill_path.relative_to(skills_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not skill_path.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    # Build zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(skill_path):
            for fname in files:
                abs_file = os.path.join(root, fname)
                arc_name = os.path.relpath(abs_file, skill_path)
                zf.write(abs_file, arcname=os.path.join(skill_name, arc_name))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{skill_name}.zip"',
        },
    )


@router.post("/v1/chat/react-agent")
async def chat_react_agent(
    dialogue: ConversationVo = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(
        "chat_react_agent:%s,%s,%s",
        dialogue.chat_mode,
        dialogue.select_param,
        dialogue.model_name,
    )
    dialogue.user_name = user_token.user_id if user_token else dialogue.user_name
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    try:
        return StreamingResponse(
            _react_agent_stream(dialogue),
            headers=headers,
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception("React Agent Exception!%s", dialogue, exc_info=e)

        async def error_text(err_msg):
            yield f"data:{err_msg}\n\n"

        return StreamingResponse(
            error_text(str(e)),
            headers=headers,
            media_type="text/plain",
        )
