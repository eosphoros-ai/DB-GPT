# LLama.cpp Server

DB-GPT supports native [llama.cpp server](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md), 
which supports concurrent requests and continuous batching inference.


## Install dependencies

```bash
pip install -e ".[llama_cpp_server]"
```
If you want to accelerate the inference speed, and you have a GPU, you can install the following dependencies:

```bash
CMAKE_ARGS="-DGGML_CUDA=ON" pip install -e ".[llama_cpp_server]"
```

## Download the model

Here, we use the `qwen2.5-0.5b-instruct` model as an example. You can download the model from the [Huggingface](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).

```bash
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true -O /tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf
````

## Modify configuration file

In the `.env` configuration file, modify the inference type of the model to start `llama.cpp` inference.

```bash
LLM_MODEL=qwen2.5-0.5b-instruct
LLM_MODEL_PATH=/tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf
MODEL_TYPE=llama_cpp_server
```

## Start the DB-GPT server

```bash
python dbgpt/app/dbgpt_server.py
```