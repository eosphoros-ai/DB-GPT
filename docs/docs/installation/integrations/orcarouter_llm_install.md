# OrcaRouter

### [OrcaRouter](https://www.orcarouter.ai) provides 150+ AI models including OpenAI, Anthropic, Gemini, DeepSeek and Qwen behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the OrcaRouter provider with DB-GPT.

1. Sign up at [OrcaRouter](https://www.orcarouter.ai) and generate an API key.
2. Set the environment variable `ORCAROUTER_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-orcarouter.toml` configuration when starting DB-GPT.

### You can look up models at [https://www.orcarouter.ai/models](https://www.orcarouter.ai/models)

### Or you can use docker/base/Dockerfile to run DB-GPT with OrcaRouter:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the OrcaRouter API key
ENV ORCAROUTER_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use OrcaRouter:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-orcarouter.toml"]
```
