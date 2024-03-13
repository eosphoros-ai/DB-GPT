#!/bin/bash

# Your api key
PROXY_API_KEY="$PROXY_API_KEY"
PROXY_SERVER_URL="${PROXY_SERVER_URL-'https://api.openai.com/v1/chat/completions'}"

docker run --gpus all -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=proxyllm \
    -e PROXY_API_KEY=$PROXY_API_KEY \
    -e PROXY_SERVER_URL=$PROXY_SERVER_URL \
    -e LANGUAGE=zh \
    -v /data:/data \
    -v /data/models:/app/models \
    --name dbgpt-allinone \
    eosphorosai/dbgpt-allinone