import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_chart import Vis

from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource, ResourceType
from ...resource.database import DBResource
from .. import excel_path

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


# 待分析的所有Excel文件所在目录
excel_files = find_excel_files(excel_path)


class Excel2TableInput(BaseModel):
    create_sql_list: List[str] = Field(
        ...,
        description="List of executable CREATE TABLE SQL statements, each for a table",
    )
    table_names: List[str] = Field(
        ...,
        description="List of table names corresponding to the SQL statements in order",
    )
    thought: str = Field(
        ..., description="Summary of thoughts to the user about the operation"
    )


class Excel2TableAction(Action[Excel2TableInput]):
    def __init__(self, file_paths: List[str] = [], **kwargs):
        """Initialize Excel2TableAction with list of file paths."""
        super().__init__(**kwargs)
        self.file_paths = excel_files

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the required resource type (database)."""
        return ResourceType.DB

    @property
    def render_protocol(self) -> Optional[Vis]:
        """This action doesn't need visualization protocol."""
        return None

    @property
    def out_model_type(self):
        """Return the output model type."""
        return Excel2TableInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action: create multiple tables and insert data "
        "from corresponding Excel files."""
        try:
            # 转换AI消息为输入对象
            param: Excel2TableInput = self._input_convert(ai_message, Excel2TableInput)

            # 验证输入数量是否匹配（SQL列表、表名列表、文件路径列表长度必须一致）
            if len(param.create_sql_list) != len(param.table_names):
                raise ValueError(
                    f"Number of SQL statements ({len(param.create_sql_list)}) "
                    "does not match number of table names ({len(param.table_names)})"
                )

            # 验证所有SQL是否为CREATE TABLE语句
            for sql in param.create_sql_list:
                if not sql.strip().upper().startswith("CREATE TABLE"):
                    raise ValueError(
                        f"SQL must be a CREATE TABLE statement, got: {sql}"
                    )

        except Exception:
            logger.exception(f"Input conversion failed! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error: The answer is not in the required format (need "
                "'create_sql_list', 'table_names' and 'thought' fields with "
                "matching lengths)",
            )

        try:
            # 验证数据库资源
            if not self.resource_need:
                raise ValueError("Database resource type is required but not found!")

            db_resources: List[DBResource] = DBResource.from_resource(self.resource)
            if not db_resources:
                raise ValueError("No available database resources found!")
            db = db_resources[0]

            # 处理每个表（通过索引确保SQL、表名和文件路径的对应关系）
            results = []
            for i in range(len(param.create_sql_list)):
                sql = param.create_sql_list[i]
                table_name = param.table_names[i]
                file_path = self.file_paths[i]

                print(f"Processing table: {table_name} from file: {file_path}")

                # 解析表结构
                table_fields = self.extract_table_fields(sql)
                logger.info(
                    f"Parsed table structure for {table_name}: "
                    f"{[f['name'] for f in table_fields]}"
                )

                # 执行建表SQL
                await db.async_execute(sql=sql)
                logger.info(f"Table {table_name} created successfully")

                # 读取对应Excel文件数据
                excel_headers, excel_data = read_excel_headers_and_data(file_path)

                # 生成并执行插入SQL
                insert_sql = self.generate_insert_sql(
                    table_name=table_name,
                    table_fields=table_fields,
                    excel_data=excel_data,
                )
                print(
                    f"Generated INSERT SQL for {table_name}: {insert_sql[:200]}..."
                )  # 打印前200字符
                await db.async_execute(sql=insert_sql)

                # 记录单个表的处理结果
                results.append(
                    {
                        "table_name": table_name,
                        "create_success": True,
                        "insert_success": True,
                        "field_mapping": {
                            "excel_headers": excel_headers,
                            "table_fields": [f["name"] for f in table_fields],
                        },
                    }
                )

            # 准备返回结果
            result_dict = {
                "thought": param.thought,
                "database": db._db_name,
                "tables": results,
                "total_tables": len(results),
                "success_count": len(results),  # 所有都成功才到这里
            }

            return ActionOutput(
                is_exe_success=True,
                content=json.dumps(result_dict, ensure_ascii=False),
                view=None,
                resource_type=self.resource_need.value,
                resource_value=db._db_name,
            )

        except Exception as e:
            logger.exception("Operation failed")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error: {str(e)}",
            )

    def extract_table_fields(self, create_sql: str) -> List[Dict[str, str]]:
        """
        从CREATE TABLE SQL语句中提取字段信息

        参数:
            create_sql: 包含CREATE TABLE的SQL语句

        返回:
            字段信息列表，每个元素为包含'name'和'type'的字典
        """
        # 移除SQL中的注释和多余空格
        sql_clean = re.sub(r"--.*?\n|/\*.*?\*/", "", create_sql, flags=re.DOTALL)
        sql_clean = re.sub(r"\s+", " ", sql_clean).strip()

        # 提取表名和字段部分
        match = re.match(
            r'CREATE\s+TABLE\s+[`"]?(\w+)[`"]?\s*\((.*)\)', sql_clean, re.IGNORECASE
        )
        if not match:
            raise ValueError("无效的CREATE TABLE语句")

        # 提取字段定义部分
        fields_part = match.group(2).strip()

        # 分割字段（处理括号内的嵌套情况）
        fields = []
        bracket_count = 0
        current_field = []

        for char in fields_part:
            if char == "(":
                bracket_count += 1
                current_field.append(char)
            elif char == ")":
                bracket_count -= 1
                current_field.append(char)
            elif char == "," and bracket_count == 0:
                # 遇到逗号且括号平衡时，分割字段
                field_str = "".join(current_field).strip()
                if field_str:
                    fields.append(field_str)
                current_field = []
            else:
                current_field.append(char)

        # 添加最后一个字段
        if current_field:
            field_str = "".join(current_field).strip()
            if field_str:
                fields.append(field_str)

        # 解析每个字段的名称和类型
        result = []
        for field in fields:
            # 忽略主键、外键等约束定义
            if re.match(r"^(PRIMARY KEY|FOREIGN KEY|CONSTRAINT)", field, re.IGNORECASE):
                continue

            # 提取字段名和类型
            # 处理可能的反引号或引号包裹的字段名
            field_match = re.match(
                r'^[`"\[]?(\w+)[`"\]]?\s+(.+?)(\s+|$)', field, re.IGNORECASE
            )
            if field_match:
                field_name = field_match.group(1)
                field_type = field_match.group(2).split()[0]  # 只取类型部分，忽略约束
                result.append(
                    {
                        "name": field_name,
                        "type": field_type.upper(),  # 类型转为大写
                    }
                )

        return result

    def generate_insert_sql(
        self,
        table_name: str,
        table_fields: List[Dict[str, str]],  # 按顺序排列的表字段信息
        excel_data: List[Dict[str, Any]],  # Excel数据（字典列表）
    ) -> str:
        """
        按顺序匹配字段生成INSERT语句
        逻辑：Excel数据字典的第n个键值对，对应表中第n个字段
        """
        if not excel_data:
            return ""
        # 获取表字段名列表（按创建顺序）
        field_names = [field["name"] for field in table_fields]

        # 生成VALUES部分
        values_clauses = []
        for row in excel_data:
            # 按顺序提取Excel行数据的值（关键：使用字典的插入顺序）
            row_values = list(row.values())
            print(f"row_values: {row_values}")
            # 确保字段数量匹配
            if len(row_values) != len(table_fields):
                raise ValueError(
                    f"Field count mismatch: Excel row has {len(row_values)} fields, "
                    f"table has {len(table_fields)} fields"
                )

            processed_values = []
            for idx, value in enumerate(row_values):
                field = table_fields[idx]

                # 处理空值
                if value is None:
                    processed_values.append("NULL")
                    continue

                # 处理日期类型（转为字符串）
                if isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d")

                # 处理字符串类型
                if field["type"] in ["varchar", "char", "text", "date", "datetime"]:
                    # 转义单引号
                    escaped_value = str(value).replace("'", "''")
                    processed_values.append(f"'{escaped_value}'")
                # 处理数字类型
                elif field["type"] in ["int", "float", "decimal", "double"]:
                    processed_values.append(str(value))
                # 其他类型默认按字符串处理
                else:
                    escaped_value = str(value).replace("'", "''")
                    processed_values.append(f"'{escaped_value}'")

            values_clauses.append(f"({', '.join(processed_values)})")

        # 拼接完整INSERT语句
        return (
            f"INSERT INTO {table_name} ({', '.join(field_names)})"
            + f" VALUES {', '.join(values_clauses)};"
        )


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


def read_excel_headers_and_data(
    file_path: str,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    读取Excel文件，返回表头信息和结构化数据

    参数:
        file_path: Excel文件路径（.xlsx格式）

    返回:
        Tuple[表头列表, 数据列表]
        - 表头列表: 从Excel第一行读取的列名
        - 数据列表: 每个元素是一个字典，键为表头，值为对应单元格数据（空单元格转为None）
    """
    # 验证文件是否存在
    if not Path(file_path).exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 验证文件格式
    if Path(file_path).suffix.lower() != ".xlsx":
        raise ValueError(f"不支持的文件格式: {Path(file_path).suffix}，仅支持.xlsx")

    try:
        # 读取Excel文件，第一行作为表头
        df = pd.read_excel(
            file_path,
            sheet_name=0,  # 读取第一个工作表
            engine="openpyxl",
            keep_default_na=False,  # 空单元格转为空字符串
        )
    except Exception as e:
        raise RuntimeError(f"读取Excel失败: {str(e)}")

    # 提取表头（第一行）
    headers = list(df.columns)
    if not headers:
        raise ValueError("Excel文件没有表头信息（第一行为空）")

    # 处理数据：将空字符串转为None，保持原始数据类型
    data = []
    for _, row in df.iterrows():
        row_data = {}
        for header in headers:
            value = row[header]
            # 将空单元格（空字符串）转为None
            row_data[header] = value if value != "" else None
        data.append(row_data)

    return headers, data
