Docker Install
==================================

### Docker (Experimental)

#### 1. Building Docker image

```bash
$ bash docker/build_all_images.sh
```

Review images by listing them:

```bash
$ docker images|grep db-gpt
```

Output should look something like the following:

```
db-gpt-allinone    latest     e1ffd20b85ac   45 minutes ago   14.5GB
db-gpt             latest     e36fb0cca5d9   3 hours ago      14GB
```

You can pass some parameters to docker/build_all_images.sh.
```bash
$ bash docker/build_all_images.sh \
--base-image nvidia/cuda:11.8.0-devel-ubuntu22.04 \
--pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple \
--language zh
```

You can execute the command `bash docker/build_all_images.sh --help` to see more usage.

#### 2. Run all in one docker container

**Run with local model**

```bash
$ docker run --gpus "device=0" -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=vicuna-13b \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name db-gpt-allinone \
    db-gpt-allinone
```

Open http://localhost:5000 with your browser to see the product.


- `-e LLM_MODEL=vicuna-13b`, means we use vicuna-13b as llm model, see /pilot/configs/model_config.LLM_MODEL_CONFIG
- `-v /data/models:/app/models`, means we mount the local model file directory `/data/models` to the docker container directory `/app/models`, please replace it with your model file directory.

You can see log with command:

```bash
$ docker logs db-gpt-allinone -f
```

**Run with openai interface**

```bash
$ PROXY_API_KEY="You api key"
$ PROXY_SERVER_URL="https://api.openai.com/v1/chat/completions"
$ docker run --gpus "device=0" -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=proxyllm \
    -e PROXY_API_KEY=$PROXY_API_KEY \
    -e PROXY_SERVER_URL=$PROXY_SERVER_URL \
    -e LANGUAGE=zh \
    -v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese \
    --name db-gpt-allinone \
    db-gpt-allinone
```

- `-e LLM_MODEL=proxyllm`, means we use proxy llm(openai interface, fastchat interface...)
- `-v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese`, means we mount the local text2vec model to the docker container.


Open http://localhost:5000 with your browser to see the product.
