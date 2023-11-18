from typing import Dict, List
import asyncio
import os
import sys
import time
import csv
import argparse
from pilot.configs.model_config import ROOT_PATH, LLM_MODEL_CONFIG

from pilot.model.cluster.worker.manager import (
    run_worker_manager,
    initialize_worker_manager_in_client,
    worker_manager,
    WorkerManager,
)

from pilot.model.base import ModelOutput, ModelInferenceMetrics
from pilot.model.cluster import PromptRequest
from pilot.scene.base_message import ModelMessage, ModelMessageRoleType


# model_name = "chatglm2-6b"
# model_name = "vicuna-7b-v1.5"
model_name = "baichuan2-7b"
model_path = LLM_MODEL_CONFIG[model_name]
# or vllm
model_type = "huggingface"

controller_addr = "http://127.0.0.1:5005"

result_csv_file = None

parallel_nums = [1, 2, 4, 16, 32]
# parallel_nums = [1, 2, 4]


def get_result_csv_file() -> str:
    return os.path.join(
        ROOT_PATH, f"pilot/data/{model_name}_{model_type}_benchmarks_llm.csv"
    )


input_lens = [64, 64]
output_lens = [256, 512]


prompt_file_map = {
    "11k": os.path.join(
        ROOT_PATH, "docker/examples/benchmarks/benchmarks_llm_11k_prompt.txt"
    )
}

METRICS_HEADERS = [
    # Params
    "model_name",
    "parallel_nums",
    "input_length",
    "output_length",
    # Merge parallel result
    "test_time_cost_ms",
    "test_total_tokens",
    "test_speed_per_second",
    # Detail for each task
    "start_time_ms",
    "end_time_ms",
    "current_time_ms",
    "first_token_time_ms",
    "first_completion_time_ms",
    "first_completion_tokens",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "speed_per_second",
]


def read_prompt_from_file(file_key: str) -> str:
    full_path = prompt_file_map[file_key]
    with open(full_path, "r+", encoding="utf-8") as f:
        return f.read()


def build_param(
    input_len: int,
    output_len: int,
    user_input: str,
    system_prompt: str = None,
) -> Dict:
    hist = []
    if system_prompt is not None:
        hist.append(
            ModelMessage(role=ModelMessageRoleType.SYSTEM, content=system_prompt)
        )
    hist.append(ModelMessage(role=ModelMessageRoleType.HUMAN, content=user_input))
    hist = list(h.dict() for h in hist)
    context_len = input_len + output_len
    params = {
        "prompt": user_input,
        "messages": hist,
        "model": model_name,
        "echo": False,
        "max_new_tokens": output_len,
        "context_len": context_len,
    }
    return params


async def run_batch(
    wh, input_len: int, output_len: int, parallel_num: int, output_file: str
):
    tasks = []
    prompt = read_prompt_from_file("11k")
    if model_type == "vllm":
        max_input_str_len = input_len
        if "baichuan" in model_name:
            # TODO prompt handle first
            max_input_str_len *= 2
        prompt = prompt[-max_input_str_len:]

    for _ in range(parallel_num):
        params = build_param(input_len, output_len, prompt, system_prompt="")
        tasks.append(wh.generate(params))
    print(
        f"Begin run benchmarks, model name: {model_name}, input_len: {input_len}, output_len: {output_len}, parallel_num: {parallel_num}, save result to {output_file}"
    )
    start_time_ms = time.time_ns() // 1_000_000
    results: List[ModelOutput] = await asyncio.gather(*tasks)
    end_time_ms = time.time_ns() // 1_000_000

    test_time_cost_ms = end_time_ms - start_time_ms
    test_total_tokens = 0
    rows = []
    for r in results:
        metrics = r.metrics
        if isinstance(metrics, dict):
            metrics = ModelInferenceMetrics(**metrics)
        print(r)
        test_total_tokens += metrics.total_tokens
        row_data = metrics.to_dict()
        rows.append(row_data)
    test_speed_per_second = test_total_tokens / (test_time_cost_ms / 1000.0)

    with open(output_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METRICS_HEADERS)
        if f.tell() == 0:
            # Fist time
            writer.writeheader()
        for row in rows:
            row["model_name"] = model_name
            row["parallel_nums"] = parallel_num
            row["input_length"] = input_len
            row["output_length"] = output_len
            row["test_time_cost_ms"] = test_time_cost_ms
            row["test_total_tokens"] = test_total_tokens
            row["test_speed_per_second"] = test_speed_per_second
            writer.writerow(row)
    print(
        f"input_len: {input_len}, output_len: {output_len}, parallel_num: {parallel_num}, save result to {output_file}"
    )


async def run_model(wh: WorkerManager) -> None:
    global result_csv_file
    if not result_csv_file:
        result_csv_file = get_result_csv_file()
    if os.path.exists(result_csv_file):
        os.rename(result_csv_file, f"{result_csv_file}.bak.csv")
    for parallel_num in parallel_nums:
        for input_len, output_len in zip(input_lens, output_lens):
            await run_batch(wh, input_len, output_len, parallel_num, result_csv_file)

    sys.exit(0)


def startup_llm_env():
    from fastapi import FastAPI

    app = FastAPI()
    initialize_worker_manager_in_client(
        app=app,
        model_name=model_name,
        model_path=model_path,
        run_locally=False,
        controller_addr=controller_addr,
        local_port=6000,
        start_listener=run_model,
        # system_app=system_app,
    )


def connect_to_remote_model():
    startup_llm_env()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default=model_name)
    parser.add_argument("--model_path", type=str, default=None)
    parser.add_argument("--model_type", type=str, default="huggingface")
    parser.add_argument("--result_csv_file", type=str, default=None)
    parser.add_argument("--input_lens", type=str, default="64,64,64,512,1024,1024,2048")
    parser.add_argument(
        "--output_lens", type=str, default="256,512,1024,1024,1024,2048,2048"
    )
    parser.add_argument("--parallel_nums", type=str, default="1,2,4,16,32")
    parser.add_argument(
        "--remote_model", type=bool, default=False, help="Connect to remote model"
    )
    parser.add_argument("--controller_addr", type=str, default="http://127.0.0.1:8000")
    parser.add_argument("--limit_model_concurrency", type=int, default=200)

    args = parser.parse_args()
    print(f"args: {args}")
    model_name = args.model_name
    model_path = args.model_path or LLM_MODEL_CONFIG[model_name]
    result_csv_file = args.result_csv_file
    input_lens = [int(i) for i in args.input_lens.strip().split(",")]
    output_lens = [int(i) for i in args.output_lens.strip().split(",")]
    parallel_nums = [int(i) for i in args.parallel_nums.strip().split(",")]
    remote_model = args.remote_model
    controller_addr = args.controller_addr
    limit_model_concurrency = args.limit_model_concurrency
    model_type = args.model_type
    if len(input_lens) != len(output_lens):
        raise ValueError("input_lens size must equal output_lens size")

    if remote_model:
        connect_to_remote_model()
    else:
        run_worker_manager(
            model_name=model_name,
            model_path=model_path,
            start_listener=run_model,
            limit_model_concurrency=limit_model_concurrency,
            model_type=model_type,
        )
