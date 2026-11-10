# UberLLM

### [UberLLM](https://uberllm.dev) serves chat models from OpenAI, Anthropic, Google, DeepSeek, Qwen, Z.ai and others behind a single OpenAI-compatible endpoint and one prepaid API key.

### This section describes how to use the UberLLM provider with DB-GPT.

1. Sign up at [UberLLM](https://uberllm.dev/signup) and create an API key.
2. Set the environment variable `UBERLLM_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-uberllm.toml` configuration when starting DB-GPT. Set `LLM_MODEL_NAME` to pick another model, for example `deepseek/deepseek-v4-flash` or `anthropic/claude-sonnet-4.6`.

### You can look up models and per-model prices at [https://uberllm.dev/models](https://uberllm.dev/models)

### Or you can use docker/base/Dockerfile to run DB-GPT with UberLLM:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the UberLLM API key
ENV UBERLLM_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use UberLLM:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-uberllm.toml"]
```
