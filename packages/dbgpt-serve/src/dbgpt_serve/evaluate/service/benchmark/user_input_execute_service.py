# app/services/user_input_execute_service.py
import json
import logging
import os
from typing import Dict, List, Optional, Union

from dbgpt.util.benchmarks import StorageUtil
from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
    BENCHMARK_DEFAULT_DB_SCHEMA,
    get_benchmark_manager,
)

from .data_compare_service import DataCompareService
from .file_parse_service import FileParseService
from .models import (
    AnswerExecuteModel,
    BaseInputModel,
    BenchmarkDataSets,
    BenchmarkExecuteConfig,
    BenchmarkModeTypeEnum,
    DataCompareResultEnum,
    DataCompareStrategyConfig,
    FileParseTypeEnum,
    InputType,
    OutputType,
    ReasoningResponse,
    RoundAnswerConfirmModel,
)

logger = logging.getLogger(__name__)


class UserInputExecuteService:
    def __init__(
        self, file_service: FileParseService, compare_service: DataCompareService
    ):
        self.file_service = file_service
        self.compare_service = compare_service

        # sql query timeout in seconds
        self.query_timeout = float(os.getenv("BENCHMARK_SQL_TIMEOUT", 360.0))

    def read_input_file(
        self, input_file_path: str
    ) -> Union[List[BaseInputModel], None]:
        """
        Read input file and return input data list

        Args:
            input_file_path: Input file path

        Returns:
            List[BaseInputModel]: Input data list
        """
        file_parse_type: FileParseTypeEnum = StorageUtil.get_file_parse_type(
            input_file_path
        )
        if file_parse_type == FileParseTypeEnum.EXCEL:
            input_sets: BenchmarkDataSets = self.file_service.parse_input_sets(
                input_file_path
            )
            return input_sets.data_list
        return None

    def post_dispatch(
        self,
        round_id: int,
        config: BenchmarkExecuteConfig,
        inputs: List[BaseInputModel],
        left_outputs: Optional[List[AnswerExecuteModel]],
        right_outputs: List[AnswerExecuteModel],
        input_file_path: str,
        output_file_path: str,
    ):
        try:
            if (
                config.benchmark_mode_type == BenchmarkModeTypeEnum.BUILD
                and config.compare_result_enable
            ):
                if left_outputs and right_outputs:
                    self._execute_llm_compare_result(
                        output_file_path,
                        round_id,
                        inputs,
                        left_outputs,
                        right_outputs,
                        config,
                    )
            elif (
                config.benchmark_mode_type == BenchmarkModeTypeEnum.EXECUTE
                and config.compare_result_enable
            ):
                if config.standard_file_path and right_outputs:
                    standard_sets = self.file_service.parse_standard_benchmark_sets(
                        config.standard_file_path
                    )
                    self._execute_llm_compare_result(
                        output_file_path,
                        round_id,
                        inputs,
                        standard_sets,
                        right_outputs,
                        config,
                    )
        except Exception as e:
            logger.error(f"[post_dispatch] execute compare error: {e}")

    def _execute_llm_compare_result(
        self,
        location: str,
        round_id: int,
        inputs: List[BaseInputModel],
        left_answers: List[AnswerExecuteModel],
        right_answers: List[AnswerExecuteModel],
        config: BenchmarkExecuteConfig,
    ):
        left_map = {a.serialNo: a for a in left_answers}
        # group right answers by serialNo to support multiple models per input
        right_group_map: Dict[int, List[AnswerExecuteModel]] = {}
        for a in right_answers:
            right_group_map.setdefault(a.serialNo, []).append(a)
        confirm_list: List[RoundAnswerConfirmModel] = []

        # compute unique llm_count across all right answers
        llm_codes = set(
            [a.llm_code for a in right_answers if getattr(a, "llm_code", None)]
        )
        llm_count = len(llm_codes) if llm_codes else len(right_answers)

        for inp in inputs:
            left = left_map.get(inp.serial_no)
            rights = right_group_map.get(inp.serial_no, [])

            if left is None and not rights:
                continue

            strategy_cfg = None
            standard_sql = None
            if left is not None:
                standard_sql = left.llmOutput
                if config.benchmark_mode_type == BenchmarkModeTypeEnum.EXECUTE:
                    strategy_cfg = left.strategyConfig
                else:
                    standard_result_list = []
                    if left.executeResult:
                        standard_result_list.append(left.executeResult)
                    strategy_cfg = DataCompareStrategyConfig(
                        strategy="EXACT_MATCH",
                        order_by=True,
                        standard_result=standard_result_list
                        if standard_result_list
                        else None,
                    )

            # for each right answer (per model)
            for right in rights:
                if config.compare_config and isinstance(config.compare_config, dict):
                    res = self.compare_service.compare_json_by_config(
                        left.llmOutput if left else "",
                        right.llmOutput or "",
                        config.compare_config,
                    )
                    compare_result = res.compare_result
                else:
                    if strategy_cfg is None:
                        compare_result = DataCompareResultEnum.FAILED
                    else:
                        res = self.compare_service.compare(
                            left
                            if left
                            else AnswerExecuteModel(
                                serialNo=inp.serial_no,
                                analysisModelId=inp.analysis_model_id,
                                question=inp.question,
                                llmOutput=None,
                                executeResult=None,
                            ),
                            right.executeResult,
                        )
                        compare_result = res.compare_result
                confirm = RoundAnswerConfirmModel(
                    serialNo=inp.serial_no,
                    analysisModelId=inp.analysis_model_id,
                    question=inp.question,
                    selfDefineTags=inp.self_define_tags,
                    prompt=inp.prompt,
                    standardAnswerSql=standard_sql,
                    strategyConfig=strategy_cfg,
                    llmOutput=right.llmOutput if right else None,
                    executeResult=right.executeResult if right else None,
                    errorMsg=right.errorMsg if right else None,
                    compareResult=compare_result,
                    llmCode=right.llm_code,
                )
                confirm_list.append(confirm)

        # write compare result to file
        self.file_service.write_data_compare_result(
            location,
            round_id,
            confirm_list,
            config.benchmark_mode_type == BenchmarkModeTypeEnum.EXECUTE,
            llm_count,
        )
        # summary compare result and save to db
        self._process_benchmark_summary_and_save(location, round_id, config)

    def _process_benchmark_summary_and_save(
        self, location: str, round_id: int, config: BenchmarkExecuteConfig
    ):
        """
        Process benchmark summary and save to database

        Args:
            location: File location
            round_id: Round ID
            config: Benchmark execution configuration
        """
        try:
            summary_json = (
                self.file_service.summary_and_write_multi_round_benchmark_result(
                    location, round_id
                )
            )

            results = json.loads(summary_json) if summary_json else []
            dao = BenchmarkResultDao()
            for item in results:
                llm_code = item.get("llmCode")
                right = int(item.get("right", 0))
                wrong = int(item.get("wrong", 0))
                failed = int(item.get("failed", 0))
                exception = int(item.get("exception", 0))
                dao.upsert_summary(
                    round_id,
                    location,
                    llm_code,
                    right,
                    wrong,
                    failed,
                    exception,
                    evaluate_code=config.evaluate_code,
                )
        except Exception as e:
            logger.error(
                f"[_process_benchmark_summary_and_save_to_db] summary from excel"
                f" or write db failed: {e}",
            )

    def _convert_query_result_to_column_format(
        self, result: List[Dict]
    ) -> Dict[str, List[str]]:
        """
        将查询结果从 List[Dict] 格式转换为 Dict[str, List[str]] 格式

        Args:
            result: 查询结果，格式为 [{"col1": "val1", "col2": "val2"},
             {"col1": "val3", "col2": "val4"}]

        Returns:
            转换后的结果，格式为 {"col1": ["val1", "val3"], "col2": ["val2", "val4"]}

        Raises:
            ValueError: 当输入数据为空或格式不正确时
        """
        if not result:
            return {}

        if not isinstance(result, list):
            raise ValueError(f"Expected List[Dict], got {type(result)}")

        # 检查第一行以获取列名
        if not result[0] or not isinstance(result[0], dict):
            raise ValueError("Query result must contain dictionary rows")

        # 获取所有列名（从第一行获取）
        column_names = list(result[0].keys())

        # 初始化结果字典
        column_data: Dict[str, List[str]] = {col: [] for col in column_names}

        # 遍历每一行数据
        for row_idx, row in enumerate(result):
            if not isinstance(row, dict):
                logger.warning(f"Skipping non-dict row at index {row_idx}: {row}")
                continue

            # 确保所有行都有相同的列结构
            for col in column_names:
                value = row.get(col)
                # 将所有值转换为字符串，处理None值
                if value is None:
                    column_data[col].append("")
                else:
                    column_data[col].append(str(value))

        return column_data

    async def build_output(self, config, input: InputType, response: ReasoningResponse):
        return await self._post_sql_query(input, config, response)

    async def _post_sql_query(
        self,
        input: InputType,
        config: BenchmarkExecuteConfig,
        response: ReasoningResponse,
    ) -> AnswerExecuteModel:
        content = response.content if response else ""
        sql = self._extract_sql_content(content)
        sql = self._process_sql_db_schema(sql)
        execute_result = None
        error_msg = None

        if config.execute_llm_result and sql:
            logger.info(
                f"[benchmark_task] queryResult start!, seriaNo:{input.serial_no},"
                f"question:{input.question}"
            )
            try:
                result: List[Dict] = await get_benchmark_manager().query(
                    sql, timeout=self.query_timeout
                )
                execute_result = self._convert_query_result_to_column_format(result)
            except Exception as e:
                logger.error(
                    f"[benchmark_task] queryResult error! sql = {sql}, errorMsg: {e}"
                )
                error_msg = str(e)
            logger.info("[benchmark_task] queryResult end!")
        else:
            logger.info(
                f"[benchmark_task] queryResult skip! execute_llm_result:"
                f" {config.execute_llm_result}, sql: {sql}"
            )

        return AnswerExecuteModel(
            serialNo=input.serial_no,
            analysisModelId=input.analysis_model_id,
            question=input.question,
            llmOutput=sql,
            executeResult=execute_result,
            cotTokens=response.cot_tokens if response else 0,
            errorMsg=error_msg,
            llm_code=input.llm_code,
            knowledge=input.knowledge,
            prompt=input.prompt,
        )

    def _extract_sql_content(self, content: str) -> str:
        """
        Extract Execute SQL from the LLM response content.
        """
        if not content:
            return ""

        content_upper = content.upper()

        if "WITH" in content_upper:
            # 包含 with
            with_before_upper = content_upper.split("WITH", 1)[0]
            with_before_lower = content.split("with", 1)[0]
            with_before = (
                with_before_lower if "WITH" in with_before_upper else with_before_upper
            )
            # 删除with 前面的语句
            sql = content[len(with_before) :]
            # 删除最后一个markdown格式之后的数据
            if "```" in sql.upper():
                sql = sql.split("```", 1)[0]
            # 删除qwen72b 模型输出的多余字符
            if '"}]' in sql:
                sql = sql.rsplit('"}]', 1)[0]
            return sql.strip()
        else:
            # 不包含 with，那就看是否包含 Select
            if "SELECT" in content_upper:
                select_before_upper = content_upper.split("SELECT", 1)[0]
                select_before_lower = content.split("select", 1)[0]
                select_before = (
                    select_before_lower
                    if "SELECT" in select_before_upper
                    else select_before_upper
                )
                # 删除select 前面的语句
                sql = content[len(select_before) :]
                # 删除最后一个markdown格式之后的数据
                if "```" in sql.upper():
                    sql = sql.split("```", 1)[0]
                # 删除qwen72b 模型输出的多余字符
                if '"}]' in sql:
                    sql = sql.rsplit('"}]', 1)[0]
                return sql.strip()
            else:
                logger.error(f"error sql format! content : {content}")
                return content.strip()

    def _process_sql_db_schema(self, sql: str) -> str:
        """
        Process SQL remove database schema to compatible with SQLite syntax
        """
        if not sql or not isinstance(sql, str):
            return sql

        # only replace the "ant_icube_dev." prefix
        return sql.replace(BENCHMARK_DEFAULT_DB_SCHEMA, "")

    def write_output_file(
        self,
        output_file_path: str,
        round_id: int,
        config: BenchmarkExecuteConfig,
        inputs: List[BaseInputModel],
        outputs: List[OutputType],
        start_index: int,
        offset: int,
    ) -> bool:
        """
        Write the output file

        Args:
            output_file_path: Output file path
            round_id: Round ID
            config: Benchmark configuration
            inputs: List of input data
            outputs: List of output data
            start_index: Starting index (batch start row index)
            offset: Offset(file rows offset)

        Returns:
            bool: Returns True if write is successful, False otherwise
        """
        return self.file_service.write_multi_round_benchmark_result(
            output_file_path, round_id, config, inputs, outputs, start_index, offset
        )
