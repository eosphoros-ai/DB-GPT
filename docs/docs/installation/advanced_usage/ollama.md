# ollama
ollama is a model serving platform that allows you to deploy models in a few seconds. 
It is a great tool.

### Install ollama
If your system is linux.
```bash
curl -fsSL https://ollama.com/install.sh | sh
```
other environments, please refer to the [official ollama website](https://ollama.com/).
### Pull models.
1. Pull LLM
```bash
ollama pull qwen:0.5b
```
2. Pull embedding model.
```bash
ollama pull nomic-embed-text
```

3. install ollama package.
```bash
# Use uv to install dependencies needed for Ollama proxy
uv sync --all-packages \
--extra "base" \
--extra "proxy_ollama" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Configure the model

Modify you toml config file to use the `ollama` provider.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "qwen:0.5b"
provider = "proxy/ollama"
api_base = "http://localhost:11434"
api_key = ""

[[models.embeddings]]
name = "bge-m3:latest"
provider = "proxy/ollama"
api_url = "http://localhost:11434"
api_key = ""
```