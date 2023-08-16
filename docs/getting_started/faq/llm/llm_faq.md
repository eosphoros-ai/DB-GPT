LLM USE FAQ
==================================
##### Q1:how to use openai chatgpt service
change your LLM_MODEL
````shell
LLM_MODEL=proxyllm
````

set your OPENAPI KEY
````shell
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
````

 make sure your openapi API_KEY is available
 
##### Q2 how to use MultiGPUs
DB-GPT will use all available gpu by default. And you can modify the setting `CUDA_VISIBLE_DEVICES=0,1` in `.env` file to use the specific gpu IDs.

Optionally, you can also specify the gpu ID to use before the starting command, as shown below:

````shell
# Specify 1 gpu
CUDA_VISIBLE_DEVICES=0 python3 pilot/server/dbgpt_server.py

# Specify 4 gpus
CUDA_VISIBLE_DEVICES=3,4,5,6 python3 pilot/server/dbgpt_server.py
````

You can modify the setting `MAX_GPU_MEMORY=xxGib` in `.env` file to configure the maximum memory used by each GPU.

##### Q3 Not Enough Memory

DB-GPT supported 8-bit quantization and 4-bit quantization.

You can modify the setting `QUANTIZE_8bit=True` or `QUANTIZE_4bit=True` in `.env` file to use quantization(8-bit quantization is enabled by default).

Llama-2-70b with 8-bit quantization can run with 80 GB of VRAM, and 4-bit quantization can run with 48 GB of VRAM.

Note: you need to install the latest dependencies according to [requirements.txt](https://github.com/eosphoros-ai/DB-GPT/blob/main/requirements.txt).