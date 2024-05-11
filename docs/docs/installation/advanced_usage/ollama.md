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
pip install ollama
```

### Use ollama proxy model in DB-GPT `.env` file

```bash
LLM_MODEL=ollama_proxyllm
PROXY_SERVER_URL=http://127.0.0.1:11434
PROXYLLM_BACKEND="qwen:0.5b"
PROXY_API_KEY=not_used
EMBEDDING_MODEL=proxy_ollama
proxy_ollama_proxy_server_url=http://127.0.0.1:11434
proxy_ollama_proxy_backend="nomic-embed-text:latest"
```

### run dbgpt server
```bash
python dbgpt/app/dbgpt_server.py
```