# vLLM Inference
DB-GPT supports [vLLM](https://github.com/vllm-project/vllm) inference, a fast and easy-to-use LLM inference and service library.

## Install dependencies
`vLLM` is an optional dependency in DB-GPT. You can install it manually through the following command.

```python
$ pip install -e ".[vllm]"
```

## Modify configuration file
In the `.env` configuration file, modify the inference type of the model to start `vllm` inference.
```python
LLM_MODEL=vicuna-13b-v1.5
MODEL_TYPE=vllm
```

For more information about the list of models supported by `vLLM`, please refer to the [vLLM supported model document](https://docs.vllm.ai/en/latest/models/supported_models.html#supported-models).

