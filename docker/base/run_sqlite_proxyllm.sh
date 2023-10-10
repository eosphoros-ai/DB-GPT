#!/bin/bash

# Your api key
PROXY_API_KEY="$PROXY_API_KEY"
PROXY_SERVER_URL="${PROXY_SERVER_URL-'https://api.openai.com/v1/chat/completions'}"

docker run --ipc host --gpus all -d \
    -p 5000:5000 \
    -e LOCAL_DB_TYPE=sqlite \
    -e LOCAL_DB_PATH=data/default_sqlite.db \
    -e LLM_MODEL=proxyllm \
    -e PROXY_API_KEY=$PROXY_API_KEY \
    -e PROXY_SERVER_URL=$PROXY_SERVER_URL \
    -e LANGUAGE=zh \
    -v /data:/data \
    -v /data/models:/app/models \
    --name dbgpt \
    eosphorosai/dbgpt