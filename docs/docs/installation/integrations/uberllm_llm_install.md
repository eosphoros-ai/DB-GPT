# UberLLM

### [UberLLM](https://uberllm.dev) serves chat models from OpenAI, Anthropic, Google, DeepSeek, Qwen, Z.ai and others behind a single OpenAI-compatible endpoint and one prepaid API key.

### This section describes how to use the UberLLM provider with DB-GPT.

1. Sign up at [UberLLM](https://uberllm.dev/signup) and create an API key.
2. Set the environment variable `UBERLLM_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-uberllm.toml` configuration when starting DB-GPT. Set `LLM_MODEL_NAME` to pick another model, for example `deepseek/deepseek-v4-flash` or `anthropic/claude-sonnet-4.6`.

### You can look up models and per-model prices at [https://uberllm.dev/models](https://uberllm.dev/models)

### Knowledge base (RAG)

UberLLM serves chat models only, so `configs/dbgpt-proxy-uberllm.toml` registers no embedding model. Chat works as is. To index and search a knowledge base, uncomment the `[[models.embeddings]]` block at the end of that file (a local Hugging Face model) or add any other embedding provider DB-GPT supports.

### Or you can use docker/base/Dockerfile to run DB-GPT with UberLLM:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Replace the existing `CMD` in the `Dockerfile` with this line:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-uberllm.toml"]
```

Pass the key when the container starts, so it never ends up in the image:

```bash
docker run -p 5670:5670 -e UBERLLM_API_KEY="your_uberllm_api_key" <your-image>
```
