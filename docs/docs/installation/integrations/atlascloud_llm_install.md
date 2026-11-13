# Atlas Cloud

### [Atlas Cloud](https://atlascloud.ai) serves models from DeepSeek, Qwen, Moonshot, Z.AI, Anthropic and OpenAI behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the Atlas Cloud provider with DB-GPT.

1. Sign up at [Atlas Cloud](https://atlascloud.ai) and create an API key from the [API keys page](https://atlascloud.ai/docs/api-keys).
2. Set the environment variable `ATLASCLOUD_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-atlascloud.toml` configuration when starting DB-GPT.

Model ids keep their vendor prefix — `deepseek-ai/DeepSeek-V3.1-Terminus`, `zai-org/glm-4.7`, `moonshotai/kimi-k2.6`, `Qwen/Qwen3-235B-A22B-Instruct-2507` — so set `LLM_MODEL_NAME` to the id exactly as the catalog lists it.

The catalog endpoint is public, so you can list the available ids without a key:

```bash
curl https://api.atlascloud.ai/v1/models
```

### You can look up models at [https://atlascloud.ai/models](https://atlascloud.ai/models)

### Or you can use docker/base/Dockerfile to run DB-GPT with Atlas Cloud:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Just uncomment the following line in the `Dockerfile` to use Atlas Cloud:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-atlascloud.toml"]
```

Pass the key in at run time rather than baking it into the image with `ENV` — a
key set at build time stays in the image layers and travels with anyone who pulls it:

```bash
docker run -it --rm -e ATLASCLOUD_API_KEY="your-key" -p 5670:5670 dbgpt:latest
```
