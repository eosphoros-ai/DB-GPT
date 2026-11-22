# MartLLM

### [MartLLM](https://martllm.com) serves chat models from OpenAI, Anthropic, Google, DeepSeek, Qwen, Z.ai and others behind a single OpenAI-compatible endpoint and one prepaid API key.

### This section describes how to use the MartLLM provider with DB-GPT.

1. Sign up at [MartLLM](https://martllm.com/signup) and create an API key.
2. Set the environment variable `MARTLLM_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-martllm.toml` configuration when starting DB-GPT. Set `LLM_MODEL_NAME` to pick another model, for example `deepseek/deepseek-v4-flash` or `anthropic/claude-sonnet-4.6`.

### You can look up models and per-model prices at [https://martllm.com/models](https://martllm.com/models)

### Knowledge base (RAG)

MartLLM serves chat models only, so `configs/dbgpt-proxy-martllm.toml` registers no embedding model. Chat works as is. To index and search a knowledge base, uncomment the `[[models.embeddings]]` block at the end of that file (a local Hugging Face model) or add any other embedding provider DB-GPT supports. With `name` and `provider` only, the model is downloaded from the Hugging Face model hub on first start. Uncomment `path` as well only after you have downloaded the model to that directory.

### Or you can use docker/base/Dockerfile to run DB-GPT with MartLLM:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Replace the existing `CMD` in the `Dockerfile` with this line:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-martllm.toml"]
```

Build the image, then pass the key when the container starts, so it never ends up in the image. `LLM_MODEL_NAME` is optional and picks the model; the two volumes keep the SQLite metadata and the Chroma index (`pilot/meta_data` and `pilot/data` in the config) when the container is replaced:

```bash
bash docker/base/build_image.sh --image-name dbgpt:latest

docker run -it --rm -p 5670:5670 \
  -e MARTLLM_API_KEY="your_martllm_api_key" \
  -e LLM_MODEL_NAME="deepseek/deepseek-v4-flash" \
  -v "$(pwd)/pilot/meta_data:/app/pilot/meta_data" \
  -v "$(pwd)/pilot/data:/app/pilot/data" \
  dbgpt:latest
```
