vLLM
==================================

[vLLM](https://github.com/vllm-project/vllm) is a fast and easy-to-use library for LLM inference and serving.

## Running vLLM

### Installing Dependencies

vLLM is an optional dependency in DB-GPT, and you can manually install it using the following command:

```bash
pip install -e ".[vllm]"
```

### Modifying the Configuration File

Next, you can directly modify your `.env` file to enable vllm.

```env
LLM_MODEL=vicuna-13b-v1.5
MODEL_TYPE=vllm
```
You can view the models supported by vLLM [here](https://vllm.readthedocs.io/en/latest/models/supported_models.html#supported-models)

Then you can run it according to [Run](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html#run).