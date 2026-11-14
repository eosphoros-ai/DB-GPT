# Runcrate

### [Runcrate](https://www.runcrate.ai) serves open-weight models such as DeepSeek, GLM, Qwen, Kimi and gpt-oss behind an OpenAI-compatible endpoint (`https://api.runcrate.ai/v1`) and a single API key.

### This section describes how to use the Runcrate provider with DB-GPT.

1. Sign up at [Runcrate](https://www.runcrate.ai) and create an API key at [https://www.runcrate.ai/dashboard/api-keys](https://www.runcrate.ai/dashboard/api-keys).
2. Set the environment variable `RUNCRATE_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-runcrate.toml` configuration when starting DB-GPT. The default model is `deepseek-ai/DeepSeek-V4.1-Flash`; set `LLM_MODEL_NAME` to use another one.

### You can look up models at [https://www.runcrate.ai/inference/pricing](https://www.runcrate.ai/inference/pricing), or list them with `curl https://api.runcrate.ai/v1/models`

### Or you can use docker/base/Dockerfile to run DB-GPT with Runcrate:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the Runcrate API key
ENV RUNCRATE_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use Runcrate:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-runcrate.toml"]
```
