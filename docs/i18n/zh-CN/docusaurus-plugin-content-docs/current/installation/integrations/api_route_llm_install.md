# API Route

[API Route](https://www.api-route.com) 提供 OpenAI 兼容接口，可通过同一个 API 密钥访问多个模型提供方。

## 配置

1. 在 API Route 创建 API 密钥。
2. 设置 `API_ROUTE_API_KEY`，并按需选择模型：

   ```bash
   export API_ROUTE_API_KEY="your-api-key"
   export LLM_MODEL_NAME="deepseek/deepseek-chat"
   ```

3. 使用随附的配置文件启动 DB-GPT：

   ```bash
   dbgpt start webserver --config configs/dbgpt-proxy-api-route.toml
   ```

默认接口地址为 `https://global.api-route.com/v1`。如需覆盖地址，可在模型配置中设置 `api_base`，或设置 `API_ROUTE_API_BASE` 环境变量。

模型标识符和可用模型请以 [API Route 模型列表](https://www.api-route.com/models) 为准。
