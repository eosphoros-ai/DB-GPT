---
slug: db-gpt-llama-3.1-support
title: DB-GPT Now Supports Meta Llama 3.1 Series Models
authors: fangyinc
tags: [llama, LLM]
---

We are thrilled to announce that DB-GPT now supports inference with the Meta Llama 3.1 series models!

## Introducing Meta Llama 3.1

Meta Llama 3.1 is a state-of-the-art series of language models developed by Meta AI. Designed with cutting-edge techniques, the Llama 3.1 models offer unparalleled performance and versatility. Here are some of the key highlights:

- **Variety of Models**: Meta Llama 3.1 is available in 8B, 70B, and 405B versions, each with both instruction-tuned and base models, supporting contexts up to 128k tokens.
- **Multilingual Support**: Supports 8 languages, including English, German, and French.
- **Extensive Training**: Trained on over 1.5 trillion tokens, utilizing 250 million human and synthetic samples for fine-tuning.
- **Flexible Licensing**: Permissive model output usage allows for adaptation into other large language models (LLMs).
- **Quantization Support**: Available in FP8, AWQ, and GPTQ quantized versions for efficient inference.
- **Performance**: The Llama 3 405B version has outperformed GPT-4 in several benchmarks.
- **Enhanced Efficiency**: The 8B and 70B models have seen a 12% improvement in coding and instruction-following capabilities.
- **Tool and Function Call Support**: Supports tool usage and function calling.

## How to Access Meta Llama 3.1

Your can access the Meta Llama 3.1 models according to [Access to Hugging Face](https://github.com/meta-llama/llama-models?tab=readme-ov-file#access-to-hugging-face).

For comprehensive documentation and additional details, please refer to the [model card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md).

## Using Meta Llama 3.1 in DB-GPT

Please read the [Source Code Deployment](../docs/installation/sourcecode) to learn how to install DB-GPT from source code.

Llama 3.1 needs upgrade your transformers >= 4.43.0, please upgrade your transformers:
```bash
pip install --upgrade "transformers>=4.43.0"
```

Please cd to the DB-GPT root directory:
```bash
cd DB-GPT
```

We assume that your models are stored in the `models` directory, e.g., `models/Meta-Llama-3.1-8B-Instruct`.

Then modify your `.env` file:
```env
LLM_MODEL=meta-llama-3.1-8b-instruct
# LLM_MODEL=meta-llama-3.1-70b-instruct
# LLM_MODEL=meta-llama-3.1-405b-instruct
## you can also specify the model path
# LLM_MODEL_PATH=models/Meta-Llama-3.1-8B-Instruct
## Quantization settings
# QUANTIZE_8bit=False
# QUANTIZE_4bit=True
## You can configure the maximum memory used by each GPU.
# MAX_GPU_MEMORY=16Gib
```

Then you can run the following command to start the server:
```bash
dbgpt start webserver
```

Open your browser and visit `http://localhost:5670` to use the Meta Llama 3.1 models in DB-GPT.

Enjoy the power of Meta Llama 3.1 in DB-GPT!
