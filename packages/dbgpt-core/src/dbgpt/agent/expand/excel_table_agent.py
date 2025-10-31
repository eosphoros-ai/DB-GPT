import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..core.agent import Agent, AgentMessage
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..resource.database import DBResource
from . import excel_path
from .actions.insert_action import Excel2TableAction

logger = logging.getLogger(__name__)


def find_excel_files(directory: str) -> list[str]:
    """
    查找指定目录下所有.csv和.xlsx文件，并返回它们的绝对路径

    参数:
        directory: 要搜索的目录路径

    返回:
        包含所有.csv和.xlsx文件绝对路径的列表，如果目录不存在则返回空列表
    """
    # 检查目录是否存在
    if not os.path.isdir(directory):
        print(f"错误: 目录 '{directory}' 不存在")
        return []

    # 存储结果的列表
    file_paths = []

    # 遍历目录及其子目录
    for root, dirs, files in os.walk(directory):
        for file in files:
            # 检查文件扩展名
            if file.lower().endswith((".csv", ".xlsx")):
                # 获取文件的绝对路径并添加到列表
                absolute_path = os.path.abspath(os.path.join(root, file))
                file_paths.append(absolute_path)

    return file_paths


excel_files = find_excel_files(excel_path)


class Excel2TableAgent(ConversableAgent):
    """Excel Scientist Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ExcelScientistAgent",
            category="agent",
            key="dbgpt_agent_expand_excel2table_agent_profile_name",
        ),
        role=DynConfig(
            "ExcelScientist",
            category="agent",
            key="dbgpt_agent_expand_excel2table_agent_profile_role",
        ),
        goal=DynConfig(
            "Based on the Excel table header (Chinese/English) and sample "
            "data, complete 3 core tasks: "
            "1. Field name adaptive processing: If the Excel header is "
            "already in English (snake_case/camelCase), retain it directly "
            "without translation; if it is Chinese, convert it to standard "
            "English snake_case (e.g., 产品ID→product_id); "
            "2. Field order strict alignment: The field order in the CREATE "
            "TABLE SQL must be exactly the same as the header order in the "
            "Excel table (to support subsequent data insertion by field order); "
            "3. Generate {{dialect}} database table creation SQL (including "
            "primary key, field type, length constraint) and a semantic table"
            " name (snake_case). "
            "Finally, provide the result in the specified JSON format (only "
            "table name and create SQL) to support subsequent automatic data "
            "insertion.",
            category="agent",
            key="dbgpt_agent_expand_excel2table_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Field naming: Detect English vs Chinese headers.  Keep English headers"
                " in snake_case;  translate Chinese headers to meaningful English "
                "snake_case.  Ensure uniqueness.",
                "Field order: SQL field order must strictly follow Excel header order, "
                "no rearrangement.",
                "Field completeness: All Excel headers must be included in the CREATE "
                "TABLE SQL, no omission.",
                "SQL generation: Infer field types from sample data;  specify VARCHAR "
                "length;  add PRIMARY KEY for ID fields;  apply NOT NULL "
                "where required.",
                "Table naming: Use [module]_[data_type], snake_case, ≤30 chars, avoid "
                "reserved words.",
                "History consistency: If headers were converted before, keep the same "
                "English names and order;  avoid duplicates.",
            ],
            category="agent",
            key="dbgpt_agent_expand_excel2table_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Store the data in one or more Excel tables mentioned by the user"
            " respectively in the database to facilitate subsequent "
            "statistical analysis of the data therein.",
            category="agent",
            key="dbgpt_agent_expand_excel2table_agent_profile_desc",
        ),
    )

    max_retry_count: int = 1
    language: str = "zh"

    def __init__(self, **kwargs):
        """Create a new DataScientistAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([Excel2TableAction])

    async def thinking(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        all_file_data = []
        for excel_file in excel_files:
            filename_with_ext = os.path.basename(excel_file)
            headers, table_data = read_excel_headers_and_data(excel_file)
            mdstr = data2md(headers, table_data)
            all_file_data.append((filename_with_ext, mdstr))
        message_parts = ["Excel文件中的部分数据如下："]
        for i, (filename, mdstr) in enumerate(all_file_data, 1):
            message_parts.append(f"\n文件 {i}: {filename}")
            message_parts.append(f"数据内容：\n{mdstr}")
        prompt = "\n".join(message_parts)
        result = await super().thinking(messages, sender, prompt)
        return result

    def _init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message, rely_messages)
        reply_message.context = {
            "display_type": self.actions[0].render_prompt(),
            "dialect": self.database.dialect,
        }
        return reply_message

    @property
    def database(self) -> DBResource:
        """Get the database resource."""
        dbs: List[DBResource] = DBResource.from_resource(self.resource)
        if not dbs:
            raise ValueError(
                f"Resource type {self.actions[0].resource_need} is not supported."
            )
        return dbs[0]

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify whether the current execution results meet the target expectations "
        "for multiple tables."""
        action_out = message.action_report
        if action_out is None:
            return (
                False,
                f"No executable analysis SQL is generated, {message.content}.",
            )

        if not action_out.is_exe_success:
            return (
                False,
                f"Please check your answer, {action_out.content}.",
            )

        try:
            action_reply_obj = json.loads(action_out.content)
            tables = action_reply_obj.get("tables", [])
            database = action_reply_obj.get("database")

            if not action_out.resource_value or not database:
                return (
                    False,
                    "Please check your answer, the data resource information "
                    "is not found.",
                )

            if not tables or len(tables) == 0:
                return (
                    False,
                    "No table information found in the execution result.",
                )

            # 验证每个表的数据
            for table_info in tables:
                table_name = table_info.get("table_name")
                if not table_name:
                    return (
                        False,
                        "Missing table name in execution result.",
                    )

                # 检查表格是否存在
                check_table_sql = f"""
                        SELECT COUNT(*) AS table_exists 
                        FROM sqlite_master 
                        WHERE type='table' AND name='{table_name}';
                        """
                cols, vals = await self.database.query(
                    sql=check_table_sql,
                    db=action_out.resource_value,
                )
                if not vals or vals[0][0] == 0:
                    return (
                        False,
                        f"Table {table_name} was not created successfully.",
                    )

                # 检查数据是否插入成功
                count_sql = f"SELECT COUNT(*) AS total_records FROM {table_name};"
                columns, values = await self.database.query(
                    sql=count_sql,
                    db=action_out.resource_value,
                )

                if not values or len(values) <= 0 or values[0][0] == 0:
                    return (
                        False,
                        f"Table {table_name} exists but contains no data. Please "
                        "check the data insertion process.",
                    )

                logger.info(
                    f"Table {table_name} verification success! There are "
                    f"{values[0][0]} rows of data."
                )

            # 所有表验证通过
            logger.info(f"All {len(tables)} tables verification success!")
            return True, None

        except Exception as e:
            logger.exception(f"DataScientist check exception！{str(e)}")
            return (
                False,
                f"Verification error, please re-read the historical information to "
                "fix this. "
                f"The error message is as follows: {str(e)}",
            )


def read_excel_headers_and_data(
    file_path: str, read_rows: Optional[int] = 3
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    读取Excel文件，返回表头信息和结构化数据（支持指定读取行数）

    参数:
        file_path: Excel文件路径（.xlsx格式）
        read_rows: 可选，指定读取的数据行数（不含表头）。
                   - 默认为5：仅读取前5行数据
                   - 设为None或0：读取全部数据
                   - 设为正整数N：读取前N行数据（若数据总行数不足N，则读取实际所有行）

    返回:
        Tuple[表头列表, 数据列表]
        - 表头列表: 从Excel第一行读取的列名
        - 数据列表: 每个元素是一个字典，键为表头，值为对应单元格数据（空单元格转为None）
    """
    # 1. 基础文件校验
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if Path(file_path).suffix.lower() != ".xlsx":
        raise ValueError(f"不支持的文件格式: {Path(file_path).suffix}，仅支持.xlsx")

    try:
        # 2. 读取Excel（先获取完整数据，后续按需截取）
        df = pd.read_excel(
            file_path,
            sheet_name=0,  # 读取第一个工作表
            engine="openpyxl",
            keep_default_na=False,  # 空单元格先转为空字符串，后续统一处理为None
        )
    except Exception as e:
        raise RuntimeError(f"读取Excel失败: {str(e)}")

    # 3. 表头提取与校验
    headers = list(df.columns)
    if not headers:
        raise ValueError("Excel文件没有表头信息（第一行为空）")

    # 4. 处理“读取行数”逻辑：截取指定行数的数据（不含表头）
    total_data_rows = len(df)  # 数据总行数（不含表头）
    # 若指定读取全部（None/0），则取全部数据；否则取“指定行数”与“实际总行数”的较小值
    if read_rows in (None, 0):
        target_rows = total_data_rows
    elif isinstance(read_rows, int) and read_rows > 0:
        target_rows = min(read_rows, total_data_rows)
    else:
        raise ValueError(f"参数read_rows无效：{read_rows}，仅支持正整数、None或0")

    # 截取目标行数的数据（避免读取无关行，提升效率）
    df_target = df.head(target_rows)

    # 5. 数据结构化：转为字典列表，空字符串转为None
    data = []
    for _, row in df_target.iterrows():
        row_data = {
            header: (row[header] if row[header] != "" else None) for header in headers
        }
        data.append(row_data)

    return headers, data


def data2md(headers, table_data):
    md_lines = []

    md_lines.append("| " + " | ".join(headers) + " |")
    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in table_data:
        values = []
        for h in headers:
            val = row.get(h, "")
            if hasattr(val, "strftime"):  # datetime
                values.append(val.strftime("%Y-%m-%d"))
            else:
                values.append(str(val))
        md_lines.append("| " + " | ".join(values) + " |")

    markdown_table = "\n".join(md_lines)
    return markdown_table
