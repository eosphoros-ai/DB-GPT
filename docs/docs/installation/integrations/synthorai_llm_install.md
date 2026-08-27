# Synthorai

### [Synthorai](https://synthorai.io) serves models from Anthropic, OpenAI, Google, DeepSeek, Qwen, Moonshot and Z.ai behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the Synthorai provider with DB-GPT.

1. Sign up at [Synthorai](https://synthorai.io) and generate an API key.
2. Set the environment variable `SYNTHORAI_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-synthorai.toml` configuration when starting DB-GPT.

Model ids are bare rather than vendor-prefixed — `claude-opus-5`, `gpt-5.6-sol`, `deepseek-v4-pro`, `glm-5.2` — so set `LLM_MODEL_NAME` to the id exactly as the catalog lists it.

### You can look up models at [https://synthorai.io/models/](https://synthorai.io/models/)

### Or you can use docker/base/Dockerfile to run DB-GPT with Synthorai:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the Synthorai API key
ENV SYNTHORAI_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use Synthorai:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-synthorai.toml"]
```
