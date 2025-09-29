import json
import os
from typing import List

import pandas as pd
from models import (
    AnswerExecuteModel,
    BaseInputModel,
    DataCompareResultEnum,
    DataCompareStrategyConfig,
    RoundAnswerConfirmModel,
)


class FileParseService:
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
        if not path.endswith(".jsonl"):
            raise ValueError(f"output_file_path must end with .jsonl, got {path}")
        out_path = path.replace(".jsonl", f".round{round_id}.compare.jsonl")
        with open(out_path, "w", encoding="utf-8") as f:
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
                    isExecute=is_execute,
                    llmCount=llm_count,
                )
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[write_data_compare_result] compare written to: {out_path}")

    def summary_and_write_multi_round_benchmark_result(
        self, output_path: str, round_id: int
    ) -> str:
        if not output_path.endswith(".jsonl"):
            raise ValueError(
                f"output_file_path must end with .jsonl, got {output_path}"
            )
        compare_path = output_path.replace(".jsonl", f".round{round_id}.compare.jsonl")
        right, wrong, failed, exception = 0, 0, 0, 0
        if os.path.exists(compare_path):
            with open(compare_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    cr = obj.get("compareResult")
                    if cr == DataCompareResultEnum.RIGHT.value:
                        right += 1
                    elif cr == DataCompareResultEnum.WRONG.value:
                        wrong += 1
                    elif cr == DataCompareResultEnum.FAILED.value:
                        failed += 1
                    elif cr == DataCompareResultEnum.EXCEPTION.value:
                        exception += 1
        else:
            print(f"[summary] compare file not found: {compare_path}")
        summary_path = output_path.replace(".jsonl", f".round{round_id}.summary.json")
        result = dict(right=right, wrong=wrong, failed=failed, exception=exception)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[summary] summary written to: {summary_path} -> {result}")
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
