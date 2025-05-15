# LLama.cpp Server

DB-GPT supports native [llama.cpp server](https://github.com/ggerganov/llama.cpp/blob/master/examples/server/README.md), 
which supports concurrent requests and continuous batching inference.


## Install dependencies

You can add the extra `--extra "llama_cpp_server"` to install the dependencies needed for llama-cpp server.

If you has a Nvidia GPU, you can enable the CUDA support by setting the environment variable `CMAKE_ARGS="-DGGML_CUDA=ON"`.

```bash
# Use uv to install dependencies needed for llama-cpp
# Install core dependencies and select desired extensions
CMAKE_ARGS="-DGGML_CUDA=ON" uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "llama_cpp_server" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

Otherwise, run the following command to install dependencies without CUDA support.

```bash
# Use uv to install dependencies needed for llama-cpp
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "llama_cpp_server" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## Download the model

Here, we use the `qwen2.5-0.5b-instruct` model as an example. You can download the model from the [Huggingface](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).

```bash
wget https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true -O /tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf
````

## Modify configuration file

Just modify you config file to use the `llama.cpp.server` provider.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
provider = "llama.cpp.server"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF
# path = "the-model-path-in-the-local-file-system"
path = "/tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf"
```