from typing import Dict, List
import asyncio
import os
import sys
import time
import csv
import argparse
import logging
import traceback
from dbgpt.configs.model_config import ROOT_PATH, LLM_MODEL_CONFIG
from datetime import datetime

from dbgpt.model.cluster.worker.manager import (
    run_worker_manager,
    initialize_worker_manager_in_client,
    WorkerManager,
)

from dbgpt.core import ModelOutput, ModelInferenceMetrics
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType


model_name = "vicuna-7b-v1.5"
model_path = LLM_MODEL_CONFIG[model_name]
# or vllm
model_type = "huggingface"

controller_addr = "http://127.0.0.1:5000"

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
    "gpu_nums",
    "parallel_nums",
    "input_length",
    "output_length",
    # Merge parallel result
    "test_time_cost_ms",
    "test_total_tokens",
    # avg_test_speed_per_second: (tokens / s), test_total_tokens / (test_time_cost_ms / 1000.0)
    "avg_test_speed_per_second(tokens/s)",
    # avg_first_token_latency_ms: sum(first_token_time_ms) / parallel_nums
    "avg_first_token_latency_ms",
    # avg_latency_ms: sum(end_time_ms - start_time_ms) / parallel_nums
    "avg_latency_ms",
    "gpu_mem(GiB)",
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
    context_len = input_len + output_len + 2
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
    wh: WorkerManager,
    input_len: int,
    output_len: int,
    parallel_num: int,
    output_file: str,
):
    tasks = []
    prompt = read_prompt_from_file("11k")
    if model_type == "vllm":
        max_input_str_len = input_len
        if "baichuan" in model_name:
            # TODO prompt handle first
            max_input_str_len *= 2
        prompt = prompt[-max_input_str_len:]

    # Warmup first
    params = build_param(input_len, output_len, prompt, system_prompt="")
    await wh.generate(params)

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
    first_token_latency_ms = 0
    latency_ms = 0
    gpu_nums = 0
    avg_gpu_mem = 0
    rows = []
    for r in results:
        metrics = r.metrics
        if isinstance(metrics, dict):
            metrics = ModelInferenceMetrics(**metrics)
        print(r)
        test_total_tokens += metrics.total_tokens
        first_token_latency_ms += metrics.first_token_time_ms - metrics.start_time_ms
        latency_ms += metrics.end_time_ms - metrics.start_time_ms
        row_data = metrics.to_dict()
        del row_data["collect_index"]
        if "avg_gpu_infos" in row_data:
            avg_gpu_infos = row_data["avg_gpu_infos"]
            gpu_nums = len(avg_gpu_infos)
            avg_gpu_mem = (
                sum(i["allocated_memory_gb"] for i in avg_gpu_infos) / gpu_nums
            )
            del row_data["avg_gpu_infos"]
            del row_data["current_gpu_infos"]
        rows.append(row_data)
    avg_test_speed_per_second = test_total_tokens / (test_time_cost_ms / 1000.0)
    avg_first_token_latency_ms = first_token_latency_ms / len(results)
    avg_latency_ms = latency_ms / len(results)

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
            row["avg_test_speed_per_second(tokens/s)"] = avg_test_speed_per_second
            row["avg_first_token_latency_ms"] = avg_first_token_latency_ms
            row["avg_latency_ms"] = avg_latency_ms
            row["gpu_nums"] = gpu_nums
            row["gpu_mem(GiB)"] = avg_gpu_mem
            writer.writerow(row)
    print(
        f"input_len: {input_len}, output_len: {output_len}, parallel_num: {parallel_num}, save result to {output_file}"
    )


async def run_model(wh: WorkerManager) -> None:
    global result_csv_file
    if not result_csv_file:
        result_csv_file = get_result_csv_file()
    if os.path.exists(result_csv_file):
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d")
        os.rename(result_csv_file, f"{result_csv_file}.bak_{now_str}.csv")
    for parallel_num in parallel_nums:
        for input_len, output_len in zip(input_lens, output_lens):
            try:
                await run_batch(
                    wh, input_len, output_len, parallel_num, result_csv_file
                )
            except Exception:
                msg = traceback.format_exc()
                logging.error(
                    f"Run benchmarks error, input_len: {input_len}, output_len: {output_len}, parallel_num: {parallel_num}, error message: {msg}"
                )
                if "torch.cuda.OutOfMemoryError" in msg:
                    return

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
    )


def connect_to_remote_model():
    startup_llm_env()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default=model_name)
    parser.add_argument("--model_path", type=str, default=None)
    parser.add_argument("--model_type", type=str, default="huggingface")
    parser.add_argument("--result_csv_file", type=str, default=None)
    parser.add_argument("--input_lens", type=str, default="8,8,256,1024")
    parser.add_argument("--output_lens", type=str, default="256,512,1024,1024")
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
        # Connect to remote model and run benchmarks
        connect_to_remote_model()
    else:
        # Start worker manager and run benchmarks
        run_worker_manager(
            model_name=model_name,
            model_path=model_path,
            start_listener=run_model,
            limit_model_concurrency=limit_model_concurrency,
            model_type=model_type,
        )
