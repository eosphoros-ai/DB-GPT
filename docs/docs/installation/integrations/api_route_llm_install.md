# API Route

### [API Route](https://www.api-route.com) provides 100+ AI models including OpenAI (GPT-5, o3), Anthropic Claude (Claude 3.7 Sonnet), DeepSeek (V3, R1), Google Gemini (2.5 Pro/Flash), and Qwen behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the API Route provider with DB-GPT.

1. Sign up at [API Route](https://www.api-route.com) and generate an API key.
2. Set the environment variable `API_ROUTE_API_KEY` with your key.
3. Optionally configure your desired model with `LLM_MODEL_NAME` (defaults to `deepseek/deepseek-chat`):
   ```bash
   export LLM_MODEL_NAME="deepseek/deepseek-chat"
   # Or use OpenAI GPT-5 / Claude 3.7 Sonnet:
   # export LLM_MODEL_NAME="openai/gpt-5"
   # export LLM_MODEL_NAME="anthropic/claude-3-7-sonnet"
   ```
4. Use the `configs/dbgpt-proxy-api-route.toml` configuration when starting DB-GPT.

### You can look up the complete model list at [https://www.api-route.com/models](https://www.api-route.com/models)

### Or you can use Docker to run DB-GPT with API Route:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the API Route API key
ENV API_ROUTE_API_KEY="***"
ENV LLM_MODEL_NAME="deepseek/deepseek-chat"

# Just uncomment the following line in the Dockerfile to use API Route:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-api-route.toml"]
```
