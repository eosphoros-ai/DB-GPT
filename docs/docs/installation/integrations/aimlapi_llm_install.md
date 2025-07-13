# AI/ML API

### AI/ML API provides 300+ AI models including Deepseek, Gemini, ChatGPT. The models run at enterprise-grade rate limits and uptimes.

### This section describes how to use the AI/ML API provider with DB-GPT.

1. Sign up at [AI/ML API](https://aimlapi.com/app/?utm_source=db_gpt&utm_medium=github&utm_campaign=integration) and generate an API key.
2. Set the environment variable `AIMLAPI_API_KEY` with your key.
3. Use the `configs/dbgpt-proxy-aimlapi.toml` configuration when starting DB-GPT.

### You can look up models at [https://aimlapi.com/models/](https://aimlapi.com/models/?utm_source=db_gpt&utm_medium=github&utm_campaign=integration)

### Or you can use docker/base/Dockerfile to run DB-GPT with AI/ML API:

```dockerfile
# Expose the port for the web server, if you want to run it directly from the Dockerfile
EXPOSE 5670

# Set the environment variable for the AIMLAPI API key
ENV AIMLAPI_API_KEY="***"

# Just uncomment the following line in the `Dockerfile` to use AI/ML API:
CMD ["dbgpt", "start", "webserver", "--config", "configs/dbgpt-proxy-aimlapi.toml"]
```
