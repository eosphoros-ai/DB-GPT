#!/bin/bash

default_input_lens="8,8,256,1024"
default_output_lens="256,512,1024,1024"
default_parallel_nums="1,2,4,16,32"

input_lens=${1:-$default_input_lens}
output_lens=${2:-$default_output_lens}
parallel_nums=${3:-$default_parallel_nums}

run_benchmark() {
    local model_name=$1
    local model_type=$2
    DB_GPT_MODEL_BENCHMARK=true python pilot/utils/benchmarks/llm/llm_benchmarks.py --model_name ${model_name} --model_type ${model_type} --input_lens ${input_lens} --output_lens ${output_lens} --parallel_nums ${parallel_nums}
}

run_benchmark "vicuna-7b-v1.5" "huggingface"
run_benchmark "vicuna-7b-v1.5" "vllm"
run_benchmark "baichuan2-7b" "huggingface"
run_benchmark "baichuan2-7b" "vllm"
