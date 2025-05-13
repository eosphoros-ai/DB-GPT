---
slug: db-gpt-qwen3-support
title: DB-GPT Now Supports Qwen3 Series Models
authors: fangyinc
tags: [Qwen, Qwen3, LLM]
---

We are thrilled to announce that DB-GPT now supports inference with the Qwen3 series models!

## Introducing Qwen3

Qwen3 is the latest generation of large language models in Qwen series, offering a comprehensive suite of dense and mixture-of-experts (MoE) models. Built upon extensive training, Qwen3 delivers groundbreaking advancements in reasoning, instruction-following, agent capabilities, and multilingual support, with the following key features:

- **Uniquely support of seamless switching between thinking mode** (for complex logical reasoning, math, and coding) and **non-thinking mode** (for efficient, general-purpose dialogue) **within single model**, ensuring optimal performance across various scenarios.
- **Significantly enhancement in its reasoning capabilities**, surpassing previous QwQ (in thinking mode) and Qwen2.5 instruct models (in non-thinking mode) on mathematics, code generation, and commonsense logical reasoning.
- **Superior human preference alignment**, excelling in creative writing, role-playing, multi-turn dialogues, and instruction following, to deliver a more natural, engaging, and immersive conversational experience.
- **Expertise in agent capabilities**, enabling precise integration with external tools in both thinking and unthinking modes and achieving leading performance among open-source models in complex agent-based tasks.
- **Support of 100+ languages and dialects** with strong capabilities for **multilingual instruction following** and **translation**.

## How to Access Qwen3

Your can access the Qwen3 models according to [Access to Hugging Face](https://huggingface.co/collections/Qwen/qwen3-67dd247413f0e2e4f653967f) or [ModelScope](https://modelscope.cn/collections/Qwen3-9743180bdc6b48)

## Using Qwen3 in DB-GPT

Please read the [Source Code Deployment](../docs/installation/sourcecode) to learn how to install DB-GPT from source code.

Qwen3 needs upgrade your transformers >= 4.51.0, please upgrade your transformers.

Here is the command to install the required dependencies for Qwen3:

```bash
# Use uv to install dependencies needed for Qwen3
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "cuda121" \
--extra "hf" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts" \
--extra "hf_qwen3"
```

To run DB-GPT with the local Qwen3 model. You can provide a configuration file to specify the model path and other parameters.
Here is an example configuration file `configs/dbgpt-local-qwen3.toml`:

```toml
# Model Configurations
[models]
[[models.llms]]
name = "Qwen/Qwen3-14B"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```
In the above configuration file, [[models.llms]] specifies the LLM model, and [[models.embeddings]] specifies the embedding model. If you not provide the path parameter, the model will be downloaded from the Hugging Face model hub according to the name parameter.

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-qwen3.toml
```

Open your browser and visit `http://localhost:5670` to use the Qwen3 models in DB-GPT.

Enjoy the power of Qwen3 in DB-GPT!


## Advanced Configurations

> Uniquely support of seamless switching between thinking mode (for complex logical reasoning, math, and coding) and non-thinking mode (for efficient, general-purpose dialogue) within single model, ensuring optimal performance across various scenarios.

By default, Qwen3 has thinking capabilities enabled. If you want to disable the thinking capabilities, you can set the `reasoning_model=false` configuration in your toml file.

```toml
[models]
[[models.llms]]
name = "Qwen/Qwen3-14B"
provider = "hf"
# Force the model to be used in non-thinking mode
reasoning_model = false
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```
