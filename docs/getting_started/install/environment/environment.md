Environment Parameter
==================================

```{admonition} LLM MODEL Config
LLM Model Name, see /pilot/configs/model_config.LLM_MODEL_CONFIG
* LLM_MODEL=vicuna-13b 

MODEL_SERVER_ADDRESS
* MODEL_SERVER=http://127.0.0.1:8000 
LIMIT_MODEL_CONCURRENCY

* LIMIT_MODEL_CONCURRENCY=5 

MAX_POSITION_EMBEDDINGS

* MAX_POSITION_EMBEDDINGS=4096 

QUANTIZE_QLORA

* QUANTIZE_QLORA=True

QUANTIZE_8bit

* QUANTIZE_8bit=True 
```

```{admonition} LLM PROXY Settings
OPENAI Key

* PROXY_API_KEY={your-openai-sk}
* PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions

from https://bard.google.com/     f12-> application-> __Secure-1PSID

* BARD_PROXY_API_KEY={your-bard-token}
```

```{admonition} DATABASE SETTINGS
### SQLite database (Current default database)
* LOCAL_DB_PATH=data/default_sqlite.db
* LOCAL_DB_TYPE=sqlite # Database Type default:sqlite

### MYSQL database
* LOCAL_DB_TYPE=mysql
* LOCAL_DB_USER=root
* LOCAL_DB_PASSWORD=aa12345678
* LOCAL_DB_HOST=127.0.0.1
* LOCAL_DB_PORT=3306
```

```{admonition} EMBEDDING SETTINGS
EMBEDDING MODEL Name, see /pilot/configs/model_config.LLM_MODEL_CONFIG
* EMBEDDING_MODEL=text2vec 

Embedding Chunk size, default 500

* KNOWLEDGE_CHUNK_SIZE=500 

Embedding Chunk Overlap, default 100
* KNOWLEDGE_CHUNK_OVERLAP=100

embeding recall top k,5

* KNOWLEDGE_SEARCH_TOP_SIZE=5 

embeding recall max token ,2000

* KNOWLEDGE_SEARCH_MAX_TOKEN=5 
```

```{admonition} Vector Store SETTINGS
#### Chroma
* VECTOR_STORE_TYPE=Chroma
#### MILVUS
* VECTOR_STORE_TYPE=Milvus
* MILVUS_URL=127.0.0.1
* MILVUS_PORT=19530
* MILVUS_USERNAME
* MILVUS_PASSWORD
* MILVUS_SECURE=

#### WEAVIATE
* VECTOR_STORE_TYPE=Weaviate
* WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
```

```{admonition} Vector Store SETTINGS
#### Chroma
* VECTOR_STORE_TYPE=Chroma
#### MILVUS
* VECTOR_STORE_TYPE=Milvus
* MILVUS_URL=127.0.0.1
* MILVUS_PORT=19530
* MILVUS_USERNAME
* MILVUS_PASSWORD
* MILVUS_SECURE=

#### WEAVIATE
* WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
```

```{admonition} Multi-GPU Setting
See https://developer.nvidia.com/blog/cuda-pro-tip-control-gpu-visibility-cuda_visible_devices/
If CUDA_VISIBLE_DEVICES is not configured, all available gpus will be used

* CUDA_VISIBLE_DEVICES=0

Optionally, you can also specify the gpu ID to use before the starting command

* CUDA_VISIBLE_DEVICES=3,4,5,6

You can configure the maximum memory used by each GPU.

* MAX_GPU_MEMORY=16Gib
```

```{admonition} Other Setting
#### Language Settings(influence prompt language)
* LANGUAGE=en
* LANGUAGE=zh
```

