# Opper

### [Opper](https://opper.ai) is an EU-hosted AI gateway with 700+ models from 50+ providers behind one OpenAI-compatible API and one key.

### This section describes how to use the Opper provider with DB-GPT.

1. Sign up at [Opper](https://platform.opper.ai) and create an API key.
2. Set the environment variable `OPPER_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-opper.toml` configuration when starting DB-GPT:

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-opper.toml
```

You can also connect Opper from the **Model Providers** page by pasting the key, with no config file.

### Model ids are bare names such as `claude-sonnet-4-6`, `gpt-5.5` or `deepseek-v4-pro`, and Opper picks the route for each request. Set `LLM_MODEL_NAME` to change the model. A `provider/model` id such as `anthropic/claude-sonnet-4-6` pins a single route.

### You can look up models at [https://opper.ai/models](https://opper.ai/models)

### Or you can run DB-GPT with Opper in Docker:

```bash
docker build -f docker/base/Dockerfile -t dbgpt:latest .
docker run -it --rm -e OPPER_API_KEY="your-key" -p 5670:5670 dbgpt:latest \
  dbgpt start webserver --config configs/dbgpt-proxy-opper.toml
```
