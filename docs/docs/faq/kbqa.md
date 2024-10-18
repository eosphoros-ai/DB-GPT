# KBQA FAQ

### Q1: text2vec-large-chinese not found

make sure you have download text2vec-large-chinese embedding model in right way

```tip
centos:yum install git-lfs
ubuntu:apt-get install git-lfs -y
macos:brew install git-lfs
```
```bash
cd models
git lfs clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

### Q2:How to change Vector DB Type in DB-GPT.

Update .env file and set VECTOR_STORE_TYPE.

DB-GPT currently support Chroma(Default), Milvus(>2.1), Weaviate, OceanBase vector database.
If you want to change vector db, Update your .env, set your vector store type, VECTOR_STORE_TYPE=Chroma (now only support Chroma and Milvus(>2.1), if you set Milvus, please set MILVUS_URL and MILVUS_PORT).

If you want to use OceanBase, please first start a docker container via the following command:
```shell
docker run --name=ob433 -e MODE=slim -p 2881:2881 -d quay.io/oceanbase/oceanbase-ce:4.3.3.0-100000142024101215
```

Donwload the partner package:
```shell
pip install --upgrade --quiet pyobvector
```

Check the connection to OceanBase and set the memory usage ratio for vector data:
```python
from pyobvector import ObVecClient

tmp_client = ObVecClient()
tmp_client.perform_raw_text_sql(
    "ALTER SYSTEM ob_vector_memory_limit_percentage = 30"
)
```

Then set the following variables in the .env file:
```shell
VECTOR_STORE_TYPE=OceanBase
OB_HOST=127.0.0.1
OB_PORT=2881
OB_USER=root@test
OB_DATABASE=test
## Optional
# OB_PASSWORD=
## Optional: If {OB_ENABLE_NORMALIZE_VECTOR} is set, the vector stored in OceanBase is normalized.
# OB_ENABLE_NORMALIZE_VECTOR=True
```
If you want to support more vector db, you can integrate yourself.[how to integrate](https://db-gpt.readthedocs.io/en/latest/modules/vector.html)
```commandline
#*******************************************************************#
#**                  VECTOR STORE SETTINGS                       **#
#*******************************************************************#
VECTOR_STORE_TYPE=Chroma
#MILVUS_URL=127.0.0.1
#MILVUS_PORT=19530
#MILVUS_USERNAME
#MILVUS_PASSWORD
#MILVUS_SECURE=

#WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
```
### Q3:When I use vicuna-13b, found some illegal character like this.
<p align="left">
  <img src="https://github.com/eosphoros-ai/DB-GPT/assets/13723926/088d1967-88e3-4f72-9ad7-6c4307baa2f8" width="800px" />
</p>

Set KNOWLEDGE_SEARCH_TOP_SIZE smaller or set KNOWLEDGE_CHUNK_SIZE smaller, and reboot server.

### Q4:space add error (pymysql.err.OperationalError) (1054, "Unknown column 'knowledge_space.context' in 'field list'")

1.shutdown dbgpt_server(ctrl c)

2.add column context for table knowledge_space

```commandline
mysql -h127.0.0.1 -uroot -p {your_password}
```

3.execute sql ddl

```commandline
mysql> use knowledge_management;
mysql> ALTER TABLE knowledge_space ADD COLUMN context TEXT COMMENT "arguments context";
```

4.restart dbgpt serve

### Q5:Use Mysql, how to use DB-GPT KBQA

build Mysql KBQA system database schema.

```bash
$ mysql -h127.0.0.1 -uroot -p{your_password} < ./assets/schema/knowledge_management.sql
```