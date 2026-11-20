# DaoXE

### [DaoXE](https://daoxe.com) serves models from Anthropic, OpenAI, Google, DeepSeek, Qwen, Moonshot, Z.ai and xAI behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the DaoXE provider with DB-GPT.

1. Sign up at [DaoXE](https://daoxe.com) and generate an API key.
2. Set the environment variable `DAOXE_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-daoxe.toml` configuration when starting DB-GPT.

Model ids are bare rather than vendor-prefixed — `claude-opus-4-8`, `gpt-5.4`, `deepseek-v4-pro`, `glm-5.2` — so set `LLM_MODEL_NAME` to the id exactly as the catalog lists it.

### You can look up models at [https://daoxe.com/pricing](https://daoxe.com/pricing)

### Or you can use docker/base/Dockerfile to run DB-GPT with DaoXE:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Just uncomment the following line in the `Dockerfile` to use DaoXE:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-daoxe.toml"]
```

Pass the key in at run time rather than baking it into the image with `ENV` — a
key set at build time stays in the image layers and travels with anyone who pulls it:

```bash
docker build -t dbgpt-daoxe:latest .
docker run -it --rm -e DAOXE_API_KEY="your-key" -p 5670:5670 dbgpt-daoxe:latest
```
