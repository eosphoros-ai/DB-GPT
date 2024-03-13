#!/bin/bash

docker run --ipc host --gpus all -d \
    -p 5000:5000 \
    -e LOCAL_DB_TYPE=sqlite \
    -e LOCAL_DB_PATH=data/default_sqlite.db \
    -e LLM_MODEL=vicuna-13b-v1.5 \
    -e LANGUAGE=zh \
    -v /data:/data \
    -v /data/models:/app/models \
    --name dbgpt \
    eosphorosai/dbgpt