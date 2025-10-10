import io
import json
import logging
from typing import List

import pandas as pd
from openpyxl.reader.excel import load_workbook

from dbgpt.util.benchmarks.ExcelUtils import ExcelUtils
from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao

from .models import (
    AnswerExecuteModel,
    BaseInputModel,
    BenchmarkDataSets,
    DataCompareStrategyConfig,
    RoundAnswerConfirmModel,
)

logger = logging.getLogger(__name__)


class FileParseService:
    def __init__(self):
        self._benchmark_dao = BenchmarkResultDao()

    def parse_input_sets(self, path: str) -> List[BaseInputModel]:
        data = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                data.append(
                    BaseInputModel(
                        serialNo=obj["serialNo"],
                        analysisModelId=obj["analysisModelId"],
                        question=obj["question"],
                        selfDefineTags=obj.get("selfDefineTags"),
                        prompt=obj.get("prompt"),
                        knowledge=obj.get("knowledge"),
                    )
                )
        return data

    def parse_llm_outputs(self, path: str) -> List[AnswerExecuteModel]:
        data = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                data.append(AnswerExecuteModel.from_dict(obj))
        return data

    def write_data_compare_result(
        self,
        path: str,
        round_id: int,
        confirm_models: List[RoundAnswerConfirmModel],
        is_execute: bool,
        llm_count: int,
    ):
        mode = "EXECUTE" if is_execute else "BUILD"
        records = []
        for cm in confirm_models:
            row = dict(
                serialNo=cm.serialNo,
                analysisModelId=cm.analysisModelId,
                question=cm.question,
                selfDefineTags=cm.selfDefineTags,
                prompt=cm.prompt,
                standardAnswerSql=cm.standardAnswerSql,
                llmOutput=cm.llmOutput,
                executeResult=cm.executeResult,
                errorMsg=cm.errorMsg,
                compareResult=cm.compareResult.value if cm.compareResult else None,
            )
            records.append(row)
        self._benchmark_dao.write_compare_results(
            round_id=round_id,
            mode=mode,
            output_path=path,
            records=records,
            is_execute=is_execute,
            llm_count=llm_count,
        )
        print(f"[write_data_compare_result] compare written to DB for: {path}")

    def summary_and_write_multi_round_benchmark_result(
        self, output_path: str, round_id: int
    ) -> str:
        summary_id = self._benchmark_dao.compute_and_save_summary(round_id, output_path)
        summary = self._benchmark_dao.get_summary(round_id, output_path)
        result = dict(
            right=summary.right if summary else 0,
            wrong=summary.wrong if summary else 0,
            failed=summary.failed if summary else 0,
            exception=summary.exception if summary else 0,
        )
        logger.info(
            f"[summary] summary saved to DB for round={round_id},"
            f" output_path={output_path} -> {result}"
        )
        return json.dumps(result, ensure_ascii=False)

    def parse_standard_benchmark_sets(
        self, standard_excel_path: str
    ) -> List[AnswerExecuteModel]:
        df = pd.read_excel(standard_excel_path, sheet_name="Sheet1")
        outputs: List[AnswerExecuteModel] = []
        for _, row in df.iterrows():
            try:
                serial_no = int(row["编号"])
            except Exception:
                continue
            question = row.get("用户问题")
            analysis_model_id = row.get("数据集ID")
            llm_output = (
                None if pd.isna(row.get("标准答案SQL")) else str(row.get("标准答案SQL"))
            )
            order_by = True
            if not pd.isna(row.get("是否排序")):
                try:
                    order_by = bool(int(row.get("是否排序")))
                except Exception:
                    order_by = True

            std_result = None
            if not pd.isna(row.get("标准结果")):
                try:
                    std_result = json.loads(row.get("标准结果"))
                except Exception:
                    std_result = None

            strategy_config = DataCompareStrategyConfig(
                strategy="CONTAIN_MATCH",
                order_by=order_by,
                standard_result=[std_result]
                if std_result is not None
                else None,  # 使用 list
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
        return outputs


class ExcelFileParseService(FileParseService):
    def parse_input_sets(self, location: str) -> BenchmarkDataSets:
        """
        Parse input sets from excel file
        Args:
            location: File location path
        Returns:
            BenchmarkDataSets: Parsed data sets
        """
        input_stream = self.get_input_stream(location)

        if input_stream is None:
            raise RuntimeError(f"file not found! path: {location}")

        # Parse excel file to get data sets
        input_sets = BenchmarkDataSets()
        workbook = None

        try:
            workbook = load_workbook(input_stream, data_only=True)
            input_list = []

            # Get the first worksheet
            sheet = workbook.worksheets[0]

            for row_num in range(
                2, sheet.max_row + 1
            ):  # Skip header row (start from 1-based index)
                row = sheet[row_num]
                if ExcelUtils.is_row_empty(row):
                    continue

                # Get content from columns 1-6 (0-based index 0-5)
                serial_no_cell = row[0]
                analysis_model_id_cell = row[1]
                question_cell = row[2]
                self_define_tags_cell = row[3]
                knowledge_cell = row[4]
                llm_output_cell = row[5]
                prompt_cell = row[8]

                # Build input model
                input_model = BaseInputModel(
                    serial_no=int(
                        ExcelUtils.get_cell_value_as_string(serial_no_cell) or "0"
                    ),
                    analysis_model_id=ExcelUtils.get_cell_value_as_string(
                        analysis_model_id_cell
                    ),
                    question=ExcelUtils.get_cell_value_as_string(question_cell),
                    self_define_tags=ExcelUtils.get_cell_value_as_string(
                        self_define_tags_cell
                    ),
                    llm_output=ExcelUtils.get_cell_value_as_string(llm_output_cell),
                    knowledge=ExcelUtils.get_cell_value_as_string(knowledge_cell),
                    prompt=ExcelUtils.get_cell_value_as_string(prompt_cell),
                )

                input_list.append(input_model)

            input_sets.data_list = input_list
        except Exception as e:
            logger.error(f"parse excel error, location: {location}, errorMsg: {e}")
        finally:
            try:
                if workbook is not None:
                    workbook.close()
            except Exception as e:
                logger.error(
                    f"close workbook error, location: {location}, errorMsg: {e}"
                )

        return input_sets

    def get_input_stream(self, location: str):
        """Get input stream from location

        Args:
            location: File location path

        Returns:
            Optional[io.BytesIO]: File input stream or None if not found
        """
        try:
            with open(location, "rb") as file:
                return io.BytesIO(file.read())
        except FileNotFoundError:
            logger.error(f"file Not found with: {location}")
            return None
        except Exception as e:
            logger.error(f"Error reading file: {location}")
            return None
