import json
import os
from typing import List

import pandas as pd
from .models import (
    AnswerExecuteModel,
    BaseInputModel,
    DataCompareResultEnum,
    DataCompareStrategyConfig,
    RoundAnswerConfirmModel,
)

from dbgpt_serve.evaluate.db.benchmark_db import BenchmarkResultDao


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
        print(f"[summary] summary saved to DB for round={round_id}, output_path={output_path} -> {result}")
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
