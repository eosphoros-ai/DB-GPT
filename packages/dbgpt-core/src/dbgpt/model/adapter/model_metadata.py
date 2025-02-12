from typing import List

from dbgpt.core import ModelMetadata

COMMON_LLAMA_CPP_MODELS = [
    ModelMetadata(
        model=[
            "Qwen/Qwen2.5-Coder-32B-Instruct-GGUF",
            "Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
            "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
            "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
            "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
            "Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        ],
        context_length=32 * 1024,
        description="Qwen 2.5 Coder by Qwen",
        function_calling=True,
    )
    # More models can be found at: https://huggingface.co/
]

COMMON_HF_MODELS = []


def _register_common_hf_models(models: List[ModelMetadata]) -> None:
    global COMMON_HF_MODELS
    COMMON_HF_MODELS.extend(models)


COMMON_HF_DEEPSEEK__MODELS = [
    ModelMetadata(
        model=[
            "deepseek-ai/DeepSeek-R1",
            "deepseek-ai/DeepSeek-R1-Zero",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
            "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        ],
        context_length=128 * 1024,
        max_output_length=8 * 1024,
        description="DeepSeek-R1 by DeepSeek",
        link="https://huggingface.co/deepseek-ai/DeepSeek-R1",
        function_calling=True,
    ),
    ModelMetadata(
        model=["deepseek-ai/DeepSeek-V3"],
        context_length=128 * 1024,
        max_output_length=8 * 1024,
        description="DeepSeek-V3 by DeepSeek",
        link="https://huggingface.co/deepseek-ai/DeepSeek-V3",
        function_calling=True,
    ),
]
COMMON_HF_QWEN25_MODELS = [
    ModelMetadata(
        model=[
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "Qwen/Qwen2.5-Coder-14B-Instruct",
            "Qwen/Qwen2.5-Coder-7B-Instruct",
            "Qwen/Qwen2.5-Coder-3B-Instruct",
            "Qwen/Qwen2.5-Coder-1.5B-Instruct",
            "Qwen/Qwen2.5-Coder-0.5B-Instruct",
        ],
        context_length=128 * 1024,
        max_output_length=8 * 1024,
        description="Qwen 2.5 Coder by Qwen",
        link="https://huggingface.co/collections/Qwen/qwen25-coder-66eaa22e6f99801bf65b0c2f",  # noqa
        function_calling=True,
    ),
    ModelMetadata(
        model=[
            "Qwen/Qwen2.5-72B-Instruct",
            "Qwen/Qwen2.5-32B-Instruct",
            "Qwen/Qwen2.5-14B-Instruct",
            "Qwen/Qwen2.5-7B-Instruct",
            "Qwen/Qwen2.5-3B-Instruct",
            "Qwen/Qwen2.5-1.5B-Instruct",
            "Qwen/Qwen2.5-0.5B-Instruct",
        ],
        context_length=128 * 1024,
        max_output_length=8 * 1024,
        description="Qwen 2.5 by Qwen",
        link="https://huggingface.co/collections/Qwen/qwen25-66e81a666513e518adb90d9e",
        function_calling=True,
    ),
]
COMMON_HF_GLM_MODELS = [
    ModelMetadata(
        model=[
            "THUDM/glm-4-9b-chat-hf",
        ],
        context_length=128 * 1024,
        max_output_length=4 * 1024,
        description="GLM-4 by Zhipu AI",
        link="https://huggingface.co/collections/THUDM/glm-4-665fcf188c414b03c2f7e3b7",
        function_calling=True,
    ),
    ModelMetadata(
        model=[
            "THUDM/glm-4-9b-chat-1m-hf",
        ],
        context_length=1000 * 1024,
        max_output_length=4 * 1024,
        description="GLM-4 by Zhipu AI",
        link="https://huggingface.co/collections/THUDM/glm-4-665fcf188c414b03c2f7e3b7",
        function_calling=True,
    ),
]

_register_common_hf_models(COMMON_HF_QWEN25_MODELS)
_register_common_hf_models(COMMON_HF_DEEPSEEK__MODELS)
_register_common_hf_models(COMMON_HF_GLM_MODELS)
