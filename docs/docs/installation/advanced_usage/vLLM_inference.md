# vLLM Inference
DB-GPT supports [vLLM](https://github.com/vllm-project/vllm) inference, a fast and easy-to-use LLM inference and service library.

## Install dependencies
`vLLM` is an optional dependency in DB-GPT. You can install it by adding the extra `--extra "vllm"` when installing dependencies.

```bash
# Use uv to install dependencies needed for vllm
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "cuda121" \
--extra "vllm" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## Modify configuration file

After installing the dependencies, you can modify your configuration file to use the `vllm` provider.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "vllm"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```

For more information about the list of models supported by `vLLM`, please refer to the [vLLM supported model document](https://docs.vllm.ai/en/latest/models/supported_models.html#supported-models).

