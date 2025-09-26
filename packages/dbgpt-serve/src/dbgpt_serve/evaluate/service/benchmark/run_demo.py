from file_parse_service import FileParseService
from data_compare_service import DataCompareService
from user_input_execute_service import UserInputExecuteService
from models import BenchmarkExecuteConfig, BenchmarkModeTypeEnum

def run_build_mode():
    fps = FileParseService()
    dcs = DataCompareService()
    svc = UserInputExecuteService(fps, dcs)

    inputs = fps.parse_input_sets("data/input_round1.jsonl")
    left = fps.parse_llm_outputs("data/output_round1_modelA.jsonl")
    right = fps.parse_llm_outputs("data/output_round1_modelB.jsonl")

    config = BenchmarkExecuteConfig(
        benchmarkModeType=BenchmarkModeTypeEnum.BUILD,
        compareResultEnable=True,
        standardFilePath=None,
        compareConfig={"check":"FULL_TEXT"}
    )

    svc.post_dispatch(
        round_id=1,
        config=config,
        inputs=inputs,
        left_outputs=left,
        right_outputs=right,
        input_file_path="data/input_round1.jsonl",
        output_file_path="data/output_round1_modelB.jsonl"
    )

    fps.summary_and_write_multi_round_benchmark_result("data/output_round1_modelB.jsonl", 1)
    print("BUILD compare path:", "data/output_round1_modelB.round1.compare.jsonl")

def run_execute_mode():
    fps = FileParseService()
    dcs = DataCompareService()
    svc = UserInputExecuteService(fps, dcs)

    inputs = fps.parse_input_sets("data/input_round1.jsonl")
    right = fps.parse_llm_outputs("data/output_execute_model.jsonl")

    config = BenchmarkExecuteConfig(
        benchmarkModeType=BenchmarkModeTypeEnum.EXECUTE,
        compareResultEnable=True,
        standardFilePath="data/standard_answers.xlsx",
        compareConfig=None
    )

    svc.post_dispatch(
        round_id=1,
        config=config,
        inputs=inputs,
        left_outputs=[],
        right_outputs=right,
        input_file_path="data/input_round1.jsonl",
        output_file_path="data/output_execute_model.jsonl"
    )

    fps.summary_and_write_multi_round_benchmark_result("data/output_execute_model.jsonl", 1)
    print("EXECUTE compare path:", "data/output_execute_model.round1.compare.jsonl")

if __name__ == "__main__":
    run_build_mode()
    run_execute_mode()