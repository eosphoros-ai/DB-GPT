# app/services/user_input_execute_service.py
from typing import List
from models import (
    BaseInputModel, AnswerExecuteModel, RoundAnswerConfirmModel,
    BenchmarkExecuteConfig, BenchmarkModeTypeEnum, DataCompareResultEnum, DataCompareStrategyConfig
)
from file_parse_service import FileParseService
from data_compare_service import DataCompareService

class UserInputExecuteService:
    def __init__(self, file_service: FileParseService, compare_service: DataCompareService):
        self.file_service = file_service
        self.compare_service = compare_service

    def post_dispatch(
        self,
        round_id: int,
        config: BenchmarkExecuteConfig,
        inputs: List[BaseInputModel],
        left_outputs: List[AnswerExecuteModel],
        right_outputs: List[AnswerExecuteModel],
        input_file_path: str,
        output_file_path: str
    ):
        try:
            if config.benchmarkModeType == BenchmarkModeTypeEnum.BUILD and config.compareResultEnable:
                if left_outputs and right_outputs:
                    self._execute_llm_compare_result(output_file_path, round_id, inputs, left_outputs, right_outputs, config)
            elif config.benchmarkModeType == BenchmarkModeTypeEnum.EXECUTE and config.compareResultEnable:
                if config.standardFilePath and right_outputs:
                    standard_sets = self.file_service.parse_standard_benchmark_sets(config.standardFilePath)
                    self._execute_llm_compare_result(output_file_path, 1, inputs, standard_sets, right_outputs, config)
        except Exception as e:
            print(f"[post_dispatch] compare error: {e}")

    def _execute_llm_compare_result(
        self,
        location: str,
        round_id: int,
        inputs: List[BaseInputModel],
        left_answers: List[AnswerExecuteModel],
        right_answers: List[AnswerExecuteModel],
        config: BenchmarkExecuteConfig
    ):
        left_map = {a.serialNo: a for a in left_answers}
        right_map = {a.serialNo: a for a in right_answers}
        confirm_list: List[RoundAnswerConfirmModel] = []

        for inp in inputs:
            left = left_map.get(inp.serialNo)
            right = right_map.get(inp.serialNo)

            if left is None and right is None:
                continue

            strategy_cfg = None
            standard_sql = None
            if left is not None:
                standard_sql = left.llmOutput
                if config.benchmarkModeType == BenchmarkModeTypeEnum.EXECUTE:
                    strategy_cfg = left.strategyConfig
                else:
                    standard_result_list = []
                    if left.executeResult:
                        standard_result_list.append(left.executeResult)
                    strategy_cfg = DataCompareStrategyConfig(
                        strategy="EXACT_MATCH",
                        order_by=True,
                        standard_result=standard_result_list if standard_result_list else None
                    )

            if right is not None:
                if config.compareConfig and isinstance(config.compareConfig, dict):
                    res = self.compare_service.compare_json_by_config(
                        left.llmOutput if left else "", right.llmOutput or "", config.compareConfig
                    )
                    compare_result = res.compare_result
                else:
                    if strategy_cfg is None:
                        compare_result = DataCompareResultEnum.FAILED
                    else:
                        res = self.compare_service.compare(
                            left if left else AnswerExecuteModel(
                                serialNo=inp.serialNo,
                                analysisModelId=inp.analysisModelId,
                                question=inp.question,
                                llmOutput=None,
                                executeResult=None
                            ),
                            right.executeResult
                        )
                        compare_result = res.compare_result
                confirm = RoundAnswerConfirmModel(
                    serialNo=inp.serialNo,
                    analysisModelId=inp.analysisModelId,
                    question=inp.question,
                    selfDefineTags=inp.selfDefineTags,
                    prompt=inp.prompt,
                    standardAnswerSql=standard_sql,
                    strategyConfig=strategy_cfg,
                    llmOutput=right.llmOutput if right else None,
                    executeResult=right.executeResult if right else None,
                    errorMsg=right.errorMsg if right else None,
                    compareResult=compare_result
                )
                confirm_list.append(confirm)

        self.file_service.write_data_compare_result(location, round_id, confirm_list, config.benchmarkModeType == BenchmarkModeTypeEnum.EXECUTE, 2)