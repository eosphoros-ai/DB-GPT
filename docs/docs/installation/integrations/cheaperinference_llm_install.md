# Cheaper Inference

### [Cheaper Inference](https://cheaperinference.com) is an OpenAI-compatible LLM gateway that serves models from OpenAI, Anthropic, Google, DeepSeek, Z.ai, Moonshot, Qwen and others behind a single endpoint and API key.

### This section describes how to use the Cheaper Inference provider with DB-GPT.

1. Sign up at [Cheaper Inference](https://cheaperinference.com/signup) and generate an API key.
2. Set the environment variable `CHEAPER_INFERENCE_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-cheaperinference.toml` configuration when starting DB-GPT.

You can also add it in the web UI.
Open **Models**, select **Cheaper Inference**, enter your API key, and click **Connect**.

Model ids are bare rather than vendor-prefixed — `gpt-5.4`, `claude-opus-5`, `gemini-3.1-pro`, `deepseek-v4-pro` — so set `LLM_MODEL_NAME` to the id exactly as the catalog lists it.

Cheaper Inference serves chat models only and has no embeddings endpoint. If you use knowledge-base features, add a `[[models.embeddings]]` entry for another provider to the configuration.

### You can look up models at [https://cheaperinference.com/#models](https://cheaperinference.com/#models)

### Or you can use docker/base/Dockerfile to run DB-GPT with Cheaper Inference:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Just uncomment the following line in the `Dockerfile` to use Cheaper Inference:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-cheaperinference.toml"]
```

Pass the key in at run time rather than baking it into the image with `ENV` — a
key set at build time stays in the image layers and travels with anyone who pulls it:

```bash
docker run -it --rm -e CHEAPER_INFERENCE_API_KEY="your-key" -p 5670:5670 dbgpt:latest
```
