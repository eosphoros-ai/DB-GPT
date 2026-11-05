# Y-API

### [Y-API](https://y-api.bestvirtualgoods.com) provides several vendors — DeepSeek, Z.ai GLM, Moonshot Kimi, Tencent Hunyuan, Xiaomi MiMo and OpenAI GPT — behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the Y-API provider with DB-GPT.

1. Sign up at [Y-API](https://y-api.bestvirtualgoods.com) and generate an API key.
2. Set the environment variable `YAPI_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-y-api.toml` configuration when starting DB-GPT.

### Model names keep their vendor prefix, for example `deepseek/deepseek-v4-flash`, `z-ai/glm-5.3` or `openai/gpt-5.6-sol`.

### You can look up models at [https://y-api.bestvirtualgoods.com/models](https://y-api.bestvirtualgoods.com/models)

### Or you can use docker/base/Dockerfile to run DB-GPT with Y-API:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the Y-API key
ENV YAPI_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use Y-API:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-y-api.toml"]
```
