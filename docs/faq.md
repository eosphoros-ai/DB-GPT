# FAQ
##### Q1: text2vec-large-chinese not found

##### A1: make sure you have download text2vec-large-chinese embedding model in right way

```tip
centos:yum install git-lfs
ubuntu:apt-get install git-lfs -y
macos:brew install git-lfs
```
```bash
cd models
git lfs clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

##### Q2: execute `pip install -r requirements.txt` error, found some package cannot find correct version.


##### A2: change the pip source.

```bash
# pypi
$ pip install -r requirements.txt -i https://pypi.python.org/simple
```

or

```bash
# tsinghua
$ pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

or

```bash
# aliyun
$ pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/
```


##### Q3:Access denied for user 'root@localhost'(using password :NO)

##### A3: make sure you have installed mysql instance in right way

Docker:
```bash
docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=aa12345678 -dit mysql:latest
```
Normal:
[download mysql instance](https://dev.mysql.com/downloads/mysql/)

##### Q4:When I use openai(MODEL_SERVER=proxyllm) to chat
<p align="left">
  <img src="https://github.com/eosphoros-ai/DB-GPT/assets/13723926/d8128b6c-e9ab-42d4-84bc-5e0d42f148c6"
 width="800px" />
</p>

##### A4: make sure your openapi API_KEY is available

##### Q5:When I Chat Data and Chat Meta Data, I found the error
<p align="left">
  <img src="https://github.com/eosphoros-ai/DB-GPT/assets/13723926/991dbaf5-da42-4c63-a65c-9aa9e174da59" width="800px" />
</p>![chatdataerror](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/991dbaf5-da42-4c63-a65c-9aa9e174da59)
]()


##### A5: you have not create your database and table
1.create your database.
```bash
mysql> create database {$your_name}
mysql> use {$your_name}
```

2.create table {$your_table} and insert your data. 
eg:
```bash
mysql>CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL COMMENT '用户名',
  `password` varchar(50) NOT NULL COMMENT '密码',
  `email` varchar(50) NOT NULL COMMENT '邮箱',
  `phone` varchar(20) DEFAULT NULL COMMENT '电话',
  PRIMARY KEY (`id`),
  KEY `idx_username` (`username`) COMMENT '索引：按用户名查询'
) ENGINE=InnoDB AUTO_INCREMENT=101 DEFAULT CHARSET=utf8mb4 COMMENT='聊天用户表'
```

##### Q6:How to change Vector DB Type in DB-GPT.

##### A6: Update .env file and set VECTOR_STORE_TYPE.
DB-GPT currently support Chroma(Default), Milvus(>2.1), Weaviate vector database.
If you want to change vector db, Update your .env, set your vector store type, VECTOR_STORE_TYPE=Chroma (now only support Chroma and Milvus(>2.1), if you set Milvus, please set MILVUS_URL and MILVUS_PORT)
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
##### Q7:When I use vicuna-13b, found some illegal character like this.
<p align="left">
  <img src="https://github.com/eosphoros-ai/DB-GPT/assets/13723926/088d1967-88e3-4f72-9ad7-6c4307baa2f8" width="800px" />
</p>

##### A7: set KNOWLEDGE_SEARCH_TOP_SIZE smaller or set KNOWLEDGE_CHUNK_SIZE smaller, and reboot server.

##### Q8:space add error (pymysql.err.OperationalError) (1054, "Unknown column 'knowledge_space.context' in 'field list'")


##### A8: 
1.shutdown dbgpt_server(ctrl c)

2.add column context for table knowledge_space
```commandline
mysql -h127.0.0.1 -uroot -paa12345678
```
3.execute sql ddl
```commandline
mysql> use knowledge_management;
mysql> ALTER TABLE knowledge_space ADD COLUMN context TEXT COMMENT "arguments context";
```
4.restart dbgpt server









