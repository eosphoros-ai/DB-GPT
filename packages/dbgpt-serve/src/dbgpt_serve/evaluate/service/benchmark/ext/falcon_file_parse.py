import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from dbgpt.util import get_or_create_event_loop
from dbgpt_serve.evaluate.service.benchmark.file_parse_service import FileParseService
from dbgpt_serve.evaluate.service.benchmark.models import (
    BaseInputModel,
    BenchmarkDataSets, AnswerExecuteModel, DataCompareStrategyConfig, EvaluationEnv,
)
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
    FileLoadResult,
    get_benchmark_manager,
)

logger = logging.getLogger(__name__)

TEXT_SQL_PROMPT = """
Given the following dataset, including field names and sampling information:
{Schema}

Containing the following knowledge:
{Knowledge}

Based on the above information, please generate the SQL for the following question:
{Query}

[Output Requirements]
* Field names in the generated SQL must use the actual field names from the table schema.
* Table names in the generated SQL must use the actual table names provided in the schema.
* Physical field names in the generated SQL must originate from the corresponding physical tables; generating fields that do not exist in the table is not allowed.
* Cartesian product calculations are not allowed in the generated SQL. This includes `CROSS JOIN`, `JOIN` operations missing `ON` or `USING` conditions, and multi-table joins without conditions set for all relationships between tables.
* The generated SQL must strictly adhere to {dialect} syntax. If it does not comply with this syntax, please regenerate it.
* Output only pure, executable SQL without any additional information.

[Example]
** Table 1 Information
*** Table Name: orders
*** DDL Statement:
    CREATE TABLE "orders" (
      "order_id" TEXT,
      "customer_id" TEXT,
      "item_type" TEXT,
      "order_date" DATE
    )
*** Field Information:
|Field Name|Field Type|Sample Data|
|:--:|:--:|:--:|
|order_id|text|CN-2025-2562,CN-2025-8623,CN-2025-6535|
|customer_id|text|52351,56263,71252|
|item_type|text|办公用品,设备,家具|
|order_date|date|2023-02-21,2024-03-30,2024-12-20|

User Question: 请帮我统计下各商品类型的订单数
Final Output SQL:
SELECT
    item_type,
    COUNT(*) as order_count
FROM
    orders
GROUP BY
    item_type;
"""


@dataclass
class BenchmarkDataItem:
    """benchmark data info item"""

    question_id: int
    db_id: str
    question: str
    sql: str
    answer: List[Dict[str, List[str]]]
    is_order: str

    @staticmethod
    def from_dict(data: dict) -> "BenchmarkDataItem":
        return BenchmarkDataItem(
            question_id=data.get("question_id", 0),
            db_id=str(data.get("db_id", "")),
            question=str(data.get("question", "")),
            sql=str(data.get("SQL", "")),
            answer=data.get("answer", []),
            is_order=data.get("is_order", "0"),
        )

@dataclass
class ColumnItem:
    """column info Item"""

    column_id: int
    column_name: str
    column_type: str
    sample_values: list

    @staticmethod
    def from_dict(data: dict) -> "ColumnItem":
        """从字典创建 ColumnItem 实例
        
        Args:
            data: 包含列信息的字典
            
        Returns:
            ColumnItem: 列信息实例
        """
        return ColumnItem(
            column_id=data.get("column_id", 0),
            column_name=data.get("column_name", ""),
            column_type=data.get("column_type", ""),
            sample_values=data.get("sample_values", []),
        )


@dataclass
class TableDDLItem:
    """Table DDL Info Item"""

    table_id: int
    table_name: str
    columns: List[ColumnItem]
    ddl: Optional[str] = None

    @staticmethod
    def from_dict(data: dict) -> "TableDDLItem":
        """从字典创建 TableDDLItem 实例
        
        Args:
            data: 包含表信息的字典
            
        Returns:
            TableDDLItem: 表信息实例
        """
        columns_data = data.get("columns", [])
        columns = [ColumnItem.from_dict(col) for col in columns_data]
        
        return TableDDLItem(
            table_id=data.get("table_id", 0),
            table_name=data.get("table_name", ""),
            columns=columns,
            ddl=data.get("ddl"),
        )


@dataclass
class TableDataItem:
    """Table Data Info Item"""

    db_id: str
    table_ddl: List[TableDDLItem]

    @staticmethod
    def from_dict(data: dict) -> "TableDataItem":
        """从字典创建 TableDataItem 实例
        
        Args:
            data: 包含数据库表信息的字典
            
        Returns:
            TableDataItem: 数据库表信息实例
        """
        tables_data = data.get("tables", [])
        table_ddl = [TableDDLItem.from_dict(table) for table in tables_data]
        
        return TableDataItem(
            db_id=str(data.get("db_id", "")),
            table_ddl=table_ddl,
        )

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


class FalconFileParseService(FileParseService):
    def __init__(self):
        super().__init__()
        self._dev_data_file = "dev_data/dev.json"
        self._dev_table_ddl_file = "dev_data/tables.json"

        self._test_data_file = "test_data/test.json"
        self._test_table_ddl_file = "test_data/tables.json"

        self.benchmark_manager = get_benchmark_manager()

        # DEV Env Data
        self._dev_data: Optional[FileLoadResult] = None
        self._dev_table_ddl: Optional[FileLoadResult] = None
        self._dev_data_loaded = False
        
        # TEST Env Data
        self._test_data: Optional[FileLoadResult] = None
        self._test_table_ddl: Optional[FileLoadResult] = None
        self._test_data_loaded = False

    @staticmethod
    def _format_answer_list(answer_list: List[Dict[str, List[str]]]) -> str:
        """格式化 answer 列表为字符串
        
        Args:
            answer_list: 答案列表，每个元素是字典，字典的值是字符串列表
            
        Returns:
            str: JSON 格式的字符串，如果列表为空则返回空字符串
        """
        if not answer_list:
            return ""
        
        try:
            import json
            # 将答案列表转换为 JSON 字符串，每个答案一行
            return "\n".join(json.dumps(item, ensure_ascii=False) for item in answer_list)
        except Exception as e:
            logger.warning(f"Failed to format answer list: {e}")
            return str(answer_list)

    def _get_env_data(self, evaluation_env: EvaluationEnv) -> Tuple[Optional[FileLoadResult], Optional[FileLoadResult]]:
        """获取指定环境的数据,如果未加载则自动加载
        Args:
            evaluation_env: 评测环境枚举(DEV 或 TEST)
        Returns:
            Tuple[Optional[FileLoadResult], Optional[FileLoadResult]]: (数据文件, 表DDL文件)
        Raises:
            RuntimeError: 如果数据加载失败
        """
        if evaluation_env == EvaluationEnv.TEST:
            # 检查 TEST 环境数据是否已加载
            if not self._test_data_loaded:
                logger.info("Loading TEST environment benchmark data for the first time...")
                try:
                    self._test_data, self._test_table_ddl = self._load_data_sync(
                        self._test_data_file,
                        self._test_table_ddl_file
                    )
                    self._test_data_loaded = True
                    logger.info("TEST environment benchmark data loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to load TEST environment benchmark data: {e}", exc_info=True)
                    raise RuntimeError(f"Failed to load TEST environment benchmark data: {e}")
            
            return self._test_data, self._test_table_ddl
        else:
            # DEV 环境(默认)
            if not self._dev_data_loaded:
                logger.info("Loading DEV environment benchmark data for the first time...")
                try:
                    self._dev_data, self._dev_table_ddl = self._load_data_sync(
                        self._dev_data_file, 
                        self._dev_table_ddl_file
                    )
                    self._dev_data_loaded = True
                    logger.info("DEV environment benchmark data loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to load DEV environment benchmark data: {e}", exc_info=True)
                    raise RuntimeError(f"Failed to load DEV environment benchmark data: {e}")
            
            return self._dev_data, self._dev_table_ddl

    def parse_input_sets(self, path: str, evaluation_env: EvaluationEnv = EvaluationEnv.DEV) -> BenchmarkDataSets:
        """
        Parse input sets from github repo
        Args:
            path: File URL path
            evaluation_env: Evaluation environment
        Returns:
            BenchmarkDataSets: Parsed data sets
        """
        # 获取环境对应的数据(如果未加载会自动加载)
        data_file, table_ddl_file = self._get_env_data(evaluation_env)
        
        try:
            # 1. 解析评测数据
            benchmark_data_list = self._parse_benchmark_data(data_file)
            if not benchmark_data_list:
                logger.error("Failed to parse benchmark data")
                return BenchmarkDataSets(data_list=[])

            # 2. 解析表结构
            table_ddl_data_list = self._parse_table_ddl_data(table_ddl_file)
            if not table_ddl_data_list:
                logger.error("Failed to parse talbe ddl data")
                return BenchmarkDataSets(data_list=[])
            table_ddl_data_map = {x.db_id: x.table_ddl for x in table_ddl_data_list}

            # 3. 将问题数据转换为 BaseInputModel 列表,并关联标准答案
            input_models = []
            for idx, question_item in enumerate(benchmark_data_list, start=1):
                input_model = BaseInputModel(
                    serial_no=question_item.question_id,
                    analysis_model_id=question_item.db_id,
                    question=question_item.question,
                    self_define_tags="",
                    knowledge="",
                    llm_output=self._format_answer_list(question_item.answer),
                    prompt=self.load_benchmark_prompt_template(question_item, table_ddl_data_map.get(question_item.db_id)),
                )
                input_models.append(input_model)
            logger.info(f"Successfully parsed {len(input_models)} question items from {evaluation_env.value} environment")
            return BenchmarkDataSets(data_list=input_models)
        except Exception as e:
            logger.error(
                f"load remote benchmark data error, error: {str(e)}",
                exc_info=True,
            )
            return BenchmarkDataSets(data_list=[])

    def parse_standard_benchmark_sets(
        self, standard_excel_path: str, evaluation_env: EvaluationEnv = EvaluationEnv.DEV
    ) -> List[AnswerExecuteModel]:
        """解析标准评测数据集
        
        Args:
            standard_excel_path: 标准Excel文件路径
            evaluation_env: 评测环境,默认为DEV
            
        Returns:
            List[AnswerExecuteModel]: 标准答案执行模型列表
        """
        # 获取环境对应的数据(如果未加载会自动加载)
        data_file, _ = self._get_env_data(evaluation_env)
        
        outputs: List[AnswerExecuteModel] = []
        # 1. 解析评测数据
        benchmark_data_list = self._parse_benchmark_data(data_file)
        if not benchmark_data_list:
            logger.error("Failed to parse benchmark data")
            return outputs

        for idx, question_item in enumerate(benchmark_data_list, start=1):
            serial_no = question_item.question_id
            question = question_item.question
            analysis_model_id = question_item.db_id
            llm_output = question_item.sql
            order_by = True
            if question_item.is_order:
                try:
                    order_by = bool(int(question_item.is_order))
                except Exception:
                    order_by = True

            std_result: Optional[List[Dict[str, List[str]]]] = None
            if question_item.answer:
                std_result = self._parse_multi_standard_result(question_item.answer)

            strategy_config = DataCompareStrategyConfig(
                strategy="CONTAIN_MATCH",
                order_by=order_by,
                standard_result=std_result if std_result is not None else None,
            )
            outputs.append(
                AnswerExecuteModel(
                    serialNo=serial_no,
                    analysisModelId=analysis_model_id,
                    question=question,
                    llmOutput=llm_output,
                    executeResult=std_result,
                    strategyConfig=strategy_config,
                )
            )
        logger.info(f"Successfully parsed {len(outputs)} standard benchmark items from {evaluation_env.value} environment")
        return outputs

    def _parse_benchmark_data(
        self, benchmark_data: Optional[FileLoadResult]
    ) -> Optional[List[BenchmarkDataItem]]:
        """
        解析问题数据
        Args:
            benchmark_data: 从 GitHub 加载的问题文件数据
        Returns:
            List[BenchmarkDataItem]: 问题数据列表，如果解析失败返回 None
        """
        if not benchmark_data or not benchmark_data.rows:
            return None

        if benchmark_data.failed_count > 0:
            logger.warning(
                f"Question data has {benchmark_data.failed_count} failed rows"
            )

        benchmark_data_list = []
        for row in benchmark_data.rows:
            if not isinstance(row.data, dict):
                logger.warning(
                    f"Row {row.line_no} data is not a dict: {type(row.data)}"
                )
                continue

            benchmark_data_item = BenchmarkDataItem.from_dict(row.data)

            if (
                not benchmark_data_item.question_id
                or not benchmark_data_item.question
                or not benchmark_data_item.db_id
            ):
                logger.warning(
                    f"Row {row.line_no} missing required fields: "
                    f"question_id={benchmark_data_item.question_id}, "
                    f"question={benchmark_data_item.question}, "
                    f"db_id={benchmark_data_item.db_id}"
                )
                continue

            benchmark_data_list.append(benchmark_data_item)

        if not benchmark_data_list:
            logger.error("No valid benchmark data parsed")
            return None

        logger.info(
            f"Successfully parsed {len(benchmark_data_list)} benchmark data"
            f" from {len(benchmark_data.rows)} rows"
        )
        return benchmark_data_list


    def _parse_table_ddl_data(
        self, table_ddl_data: Optional[FileLoadResult]
    ) -> Optional[List[TableDataItem]]:
        """
        解析表 DDL 数据
        Args:
            table_ddl_data: 从 GitHub 加载的表 DDL 数据
        Returns:
            List[TableDataItem]: 表 DDL 数据列表，如果解析失败返回 None
        """
        if not table_ddl_data or not table_ddl_data.rows:
            logger.warning("table ddl data is None")
            return None
        if table_ddl_data.failed_count > 0:
            logger.warning(
                f"table ddl data has {table_ddl_data.failed_count} failed items"
            )

        table_ddl_data_list = []
        for row in table_ddl_data.rows:
            if not isinstance(row.data, dict):
                logger.warning(
                    f"Row {row.line_no} data is not a dict: {type(row.data)}"
                )
                continue

            table_ddl_data_item = TableDataItem.from_dict(row.data)

            if (
                    not table_ddl_data_item.db_id
                    or not table_ddl_data_item.table_ddl
            ):
                logger.warning(
                    f"Row {row.line_no} missing required fields: "
                    f"db_id={table_ddl_data_item.db_id}, "
                    f"table_ddl={table_ddl_data_item.table_ddl}"
                )
                continue

            table_ddl_data_list.append(table_ddl_data_item)

        if not table_ddl_data_list:
            return None

        logger.info(
            f"Successfully parsed {len(table_ddl_data_list)} table DDL data"
            f" from {len(table_ddl_data.rows)} rows"
        )
        return table_ddl_data_list


    async def _async_load_data(
        self, data_file: str, table_ddl_file: str
    ) -> Tuple[
        Optional[FileLoadResult],
        Optional[FileLoadResult],
    ]:
        """并发加载两个文件数据

        使用 asyncio.gather 并发执行两个异步任务，提高加载效率
        
        Args:
            data_file: 数据文件路径
            table_ddl_file: 表DDL文件路径

        Returns:
            Tuple: (data, table_ddl)
        """
        data, table_ddl = await asyncio.gather(
            self.benchmark_manager.load_file_from_github(data_file),
            self.benchmark_manager.load_file_from_github(table_ddl_file),
        )
        return data, table_ddl

    def _load_data_sync(
        self, data_file: str, table_ddl_file: str
    ) -> Tuple[
        Optional[FileLoadResult],
        Optional[FileLoadResult],
    ]:
        """在同步上下文中加载数据

        智能检测当前事件循环状态：
        - 如果事件循环正在运行，使用线程池在新线程中执行异步代码
        - 如果没有运行中的事件循环，直接使用 run_until_complete
        
        Args:
            data_file: 数据文件路径
            table_ddl_file: 表DDL文件路径

        Returns:
            Tuple: (data, table_ddl)
        """
        try:
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self._async_load_data(data_file, table_ddl_file))
                return future.result()
        except RuntimeError:
            loop = get_or_create_event_loop()
            return loop.run_until_complete(self._async_load_data(data_file, table_ddl_file))

    @staticmethod
    def _build_table_schema_info(table_ddl_list: Optional[List[TableDDLItem]]) -> str:
        """构建表的 Schema 信息
        
        Args:
            table_ddl_list: 表 DDL 信息列表
            
        Returns:
            str: 格式化的表 Schema 信息字符串
        """
        if not table_ddl_list:
            return ""
        
        schema_parts = []
        
        for idx, table in enumerate(table_ddl_list, start=1):
            # 表头信息
            schema_parts.append(f"** Table {idx} Information")
            schema_parts.append(f"*** Table Name: {table.table_name}")
            
            # 如果有 DDL，添加 DDL 信息
            if table.ddl:
                schema_parts.append(f"*** DDL Statement:")
                # DDL 可能是多行的，需要缩进处理
                ddl_lines = table.ddl.strip().split('\n')
                for ddl_line in ddl_lines:
                    schema_parts.append(f"    {ddl_line}")
            
            # 列信息表头 - 使用更清晰的格式
            schema_parts.append("*** Field Information:")
            schema_parts.append("|Field Name|Field Type|Sample Data|")
            schema_parts.append("|:--:|:--:|:--:|")
            
            # 添加每一列的信息
            for column in table.columns:
                # 格式化样本值 - 限制在合理长度内
                if column.sample_values:
                    # 取前3-5个样本值，用逗号连接，避免过长
                    sample_count = min(3, len(column.sample_values))
                    sample_str = ",".join(str(val) for val in column.sample_values[:sample_count])
                    # 如果样本值过长，截断
                    if len(sample_str) > 100:
                        sample_str = sample_str[:97] + "..."
                else:
                    sample_str = "-"
                
                schema_parts.append(f"|{column.column_name}|{column.column_type}|{sample_str}|")
            
            # 表之间添加空行分隔
            if idx < len(table_ddl_list):
                schema_parts.append("")
        
        return "\n".join(schema_parts)

    def _parse_multi_standard_result(
        self, answer_list: List[Dict[str, List[str]]]
    ) -> Optional[List[Dict[str, List[str]]]]:
        """
        解析标准答案结果
        
        Args:
            answer_list: 答案列表，已经是正确的格式
            
        Returns:
            Optional[List[Dict[str, List[str]]]]: 返回答案列表，如果为空返回 None
        """
        try:
            if not answer_list:
                return None
            return answer_list if answer_list else None
        except Exception as e:
            logger.error(f"parse standard results error: {e}")
            return None

    def load_benchmark_prompt_template(self, question_item: BenchmarkDataItem, table_ddl: List[TableDDLItem]) -> str:
        """
        build benchmark prompt template
        """
        schema = self._build_table_schema_info(table_ddl)
        format_params = {
            "Schema": schema,
            "Knowledge": "",
            "Query": question_item.question
        }
        # 使用 SafeDict 和 format_map 实现非严格模式，缺失的变量不会报错
        return TEXT_SQL_PROMPT.format_map(SafeDict(format_params))