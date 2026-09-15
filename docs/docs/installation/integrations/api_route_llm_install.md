# API Route

### [API Route](https://www.api-route.com) provides 100+ AI models including OpenAI, Anthropic, Gemini, DeepSeek, and Qwen behind a single OpenAI-compatible endpoint and API key.

### This section describes how to use the API Route provider with DB-GPT.

1. Sign up at [API Route](https://www.api-route.com) and generate an API key.
2. Set the environment variable `API_ROUTE_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-api-route.toml` configuration when starting DB-GPT.

### You can look up models at [https://www.api-route.com/models](https://www.api-route.com/models)

### Or you can use docker/base/Dockerfile to run DB-GPT with API Route:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the API Route API key
ENV API_ROUTE_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use API Route:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-api-route.toml"]
```
