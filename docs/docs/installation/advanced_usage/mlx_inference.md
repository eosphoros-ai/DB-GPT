# MLX Inference
DB-GPT supports [MLX](https://github.com/ml-explore/mlx-lm) inference, a fast and easy-to-use LLM inference and service library.

## Install dependencies

`MLX` is an optional dependency in DB-GPT. You can install it by adding the extra `--extra "mlx"` when installing dependencies.

```bash
# Use uv to install dependencies needed for mlx
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "hf" \
--extra "mlx" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

## Modify configuration file

After installing the dependencies, you can modify your configuration file to use the `mlx` provider.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "Qwen/Qwen3-0.6B-MLX-4bit"
provider = "mlx"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# https://huggingface.co/Qwen/Qwen3-0.6B-MLX-4bit
# path = "the-model-path-in-the-local-file-system"
```

### Step 3: Run the Model

You can run the model using the following command:

```bash
uv run dbgpt start webserver --config {your_config_file}
```