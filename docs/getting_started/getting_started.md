# Quickstart Guide

This tutorial gives you a quick walkthrough about use DB-GPT with you environment and data.

## Installation

To get started, install DB-GPT with the following steps.

### 1. Hardware Requirements 
As our project has the ability to achieve ChatGPT performance of over 85%, there are certain hardware requirements. However, overall, the project can be deployed and used on consumer-grade graphics cards. The specific hardware requirements for deployment are as follows:

| GPU  | VRAM Size | Performance                                 |
| --------- | --------- | ------------------------------------------- |
| RTX 4090  | 24 GB     | Smooth conversation inference        |
| RTX 3090  | 24 GB     | Smooth conversation inference, better than V100 |
| V100      | 16 GB     | Conversation inference possible, noticeable stutter |

### 2. Install

1.This project relies on a local MySQL database service, which you need to install locally. We recommend using Docker for installation.
```bash
$ docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=aa12345678 -dit mysql:latest
```
2. prepare server sql script
```bash
$ mysql -h127.0.0.1 -uroot -paa12345678 < ./assets/schema/knowledge_management.sql
```

We use [Chroma embedding database](https://github.com/chroma-core/chroma) as the default for our vector database, so there is no need for special installation. If you choose to connect to other databases, you can follow our tutorial for installation and configuration. 
For the entire installation process of DB-GPT, we use the miniconda3 virtual environment. Create a virtual environment and install the Python dependencies.

```bash
python>=3.10
conda create -n dbgpt_env python=3.10
conda activate dbgpt_env
pip install -r requirements.txt
```
Before use DB-GPT Knowledge Management
```bash
python -m spacy download zh_core_web_sm

```

Once the environment is installed, we have to create a new folder "models" in the DB-GPT project, and then we can put all the models downloaded from huggingface in this directory

```{tip}
Notice make sure you have install git-lfs
```

```bash
git clone https://huggingface.co/Tribbiani/vicuna-13b 
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
git clone https://huggingface.co/THUDM/chatglm2-6b
```

The model files are large and will take a long time to download. During the download, let's configure the .env file, which needs to be copied and created from the .env.template

```{tip}
cp .env.template .env
```

You can configure basic parameters in the .env file, for example setting LLM_MODEL to the model to be used

### 3. Run
You can refer to this document to obtain the Vicuna weights: [Vicuna](https://github.com/lm-sys/FastChat/blob/main/README.md#model-weights) .

If you have difficulty with this step, you can also directly use the model from [this link](https://huggingface.co/Tribbiani/vicuna-7b) as a replacement.

set .env configuration set your vector store type, eg:VECTOR_STORE_TYPE=Chroma, now we support Chroma and Milvus(version > 2.1)


1.Run db-gpt server 

```bash
$ python pilot/server/dbgpt_server.py
```
Open http://localhost:5000 with your browser to see the product.

If you want to access an external LLM service, you need to 1.set the variables LLM_MODEL=YOUR_MODEL_NAME MODEL_SERVER=YOUR_MODEL_SERVER（eg:http://localhost:5000） in the .env file.
2.execute dbgpt_server.py in light mode

```bash
$ python pilot/server/dbgpt_server.py --light
```

If you want to learn about dbgpt-webui, read https://github.com/csunny/DB-GPT/tree/new-page-framework/datacenter

