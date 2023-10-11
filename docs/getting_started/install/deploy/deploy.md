# Installation From Source

This tutorial gives you a quick walkthrough about use DB-GPT with you environment and data.

## Installation

To get started, install DB-GPT with the following steps.

### 1. Hardware Requirements 
As our project has the ability to achieve ChatGPT performance of over 85%, there are certain hardware requirements. However, overall, the project can be deployed and used on consumer-grade graphics cards. The specific hardware requirements for deployment are as follows:

| GPU      | VRAM Size | Performance                                 |
|----------|-----------| ------------------------------------------- |
| RTX 4090 | 24 GB     | Smooth conversation inference        |
| RTX 3090 | 24 GB     | Smooth conversation inference, better than V100 |
| V100     | 16 GB     | Conversation inference possible, noticeable stutter |
| T4       | 16 GB     | Conversation inference possible, noticeable stutter |

if your VRAM Size is not enough, DB-GPT supported 8-bit quantization and 4-bit quantization.

Here are some of the VRAM size usage of the models we tested in some common scenarios.

| Model     |  Quantize | VRAM Size |
| --------- | --------- | --------- |
| vicuna-7b-v1.5  | 4-bit  | 8 GB     |
| vicuna-7b-v1.5  | 8-bit  | 12 GB     |
| vicuna-13b-v1.5  | 4-bit  | 12 GB     |
| vicuna-13b-v1.5  | 8-bit  | 20 GB     |
| llama-2-7b  | 4-bit  | 8 GB     |
| llama-2-7b  | 8-bit  | 12 GB     |
| llama-2-13b  | 4-bit  | 12 GB     | 
| llama-2-13b  | 8-bit  | 20 GB     |
| llama-2-70b  | 4-bit  | 48 GB     |
| llama-2-70b  | 8-bit  | 80 GB     |
| baichuan-7b  | 4-bit  | 8 GB     |
| baichuan-7b  | 8-bit  | 12 GB     |
| baichuan-13b  | 4-bit  | 12 GB     |
| baichuan-13b  | 8-bit  | 20 GB     |

### 2. Install
```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

We use Sqlite as default database, so there is no need for database installation.  If you choose to connect to other databases, you can follow our tutorial for installation and configuration. 
For the entire installation process of DB-GPT, we use the miniconda3 virtual environment. Create a virtual environment and install the Python dependencies.
[How to install Miniconda](https://docs.conda.io/en/latest/miniconda.html)
```bash
python>=3.10
conda create -n dbgpt_env python=3.10
conda activate dbgpt_env
pip install -e ".[default]"
```
Before use DB-GPT Knowledge
```bash
python -m spacy download zh_core_web_sm

```

Once the environment is installed, we have to create a new folder "models" in the DB-GPT project, and then we can put all the models downloaded from huggingface in this directory

```{tip}
Notice make sure you have install git-lfs

centos:yum install git-lfs

ubuntu:app-get install git-lfs

macos:brew install git-lfs
```

```bash
cd DB-GPT
mkdir models and cd models
#### llm model
git clone https://huggingface.co/lmsys/vicuna-13b-v1.5
or
git clone https://huggingface.co/THUDM/chatglm2-6b

#### embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

The model files are large and will take a long time to download. During the download, let's configure the .env file, which needs to be copied and created from the .env.template

if you want to use openai llm service, see [LLM Use FAQ](https://db-gpt.readthedocs.io/en/latest/getting_started/faq/llm/llm_faq.html)

```{tip}
cp .env.template .env
```

You can configure basic parameters in the .env file, for example setting LLM_MODEL to the model to be used

([Vicuna-v1.5](https://huggingface.co/lmsys/vicuna-13b-v1.5) based on llama-2 has been released, we recommend you set `LLM_MODEL=vicuna-13b-v1.5` to try this model)

### 3. Run

**(Optional) load examples into SQLlite**
```bash
bash ./scripts/examples/load_examples.sh
```

On windows platform:
```PowerShell
.\scripts\examples\load_examples.bat
```

1.Run db-gpt server 

```bash
python pilot/server/dbgpt_server.py
```

Open http://localhost:5000 with your browser to see the product.

```{tip}
If you want to access an external LLM service, you need to

1.set the variables LLM_MODEL=YOUR_MODEL_NAME, MODEL_SERVER=YOUR_MODEL_SERVER（eg:http://localhost:5000） in the .env file.

2.execute dbgpt_server.py in light mode
```

If you want to learn about dbgpt-webui, read https://github./csunny/DB-GPT/tree/new-page-framework/datacenter

```bash
python pilot/server/dbgpt_server.py --light
```

### Multiple GPUs

DB-GPT will use all available gpu by default. And you can modify the setting `CUDA_VISIBLE_DEVICES=0,1` in `.env` file to use the specific gpu IDs.

Optionally, you can also specify the gpu ID to use before the starting command, as shown below:

````shell
# Specify 1 gpu
CUDA_VISIBLE_DEVICES=0 python3 pilot/server/dbgpt_server.py

# Specify 4 gpus
CUDA_VISIBLE_DEVICES=3,4,5,6 python3 pilot/server/dbgpt_server.py
````

You can modify the setting `MAX_GPU_MEMORY=xxGib` in `.env` file to configure the maximum memory used by each GPU.

### Not Enough Memory

DB-GPT supported 8-bit quantization and 4-bit quantization.

You can modify the setting `QUANTIZE_8bit=True` or `QUANTIZE_4bit=True` in `.env` file to use quantization(8-bit quantization is enabled by default).

Llama-2-70b with 8-bit quantization can run with 80 GB of VRAM, and 4-bit quantization can run with 48 GB of VRAM.