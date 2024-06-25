# vLLM Inference
DB-GPT supports [vLLM](https://github.com/vllm-project/vllm) inference, a fast and easy-to-use LLM inference and service library.

## Install dependencies
`vLLM` is an optional dependency in DB-GPT. You can install it manually through the following command.

```bash
pip install -e ".[vllm]"
```

## Modify configuration file
In the `.env` configuration file, modify the inference type of the model to start `vllm` inference.
```bash
LLM_MODEL=glm-4-9b-chat
MODEL_TYPE=vllm
# modify the following configuration if you possess GPU resources
# gpu_memory_utilization=0.8
```

For more information about the list of models supported by `vLLM`, please refer to the [vLLM supported model document](https://docs.vllm.ai/en/latest/models/supported_models.html#supported-models).

