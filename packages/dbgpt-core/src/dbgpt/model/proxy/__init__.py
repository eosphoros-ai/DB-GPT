"""Proxy models."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dbgpt.model.proxy.llms.aimlapi import AimlapiLLMClient
    from dbgpt.model.proxy.llms.burncloud import BurnCloudLLMClient
    from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
    from dbgpt.model.proxy.llms.claude import ClaudeLLMClient
    from dbgpt.model.proxy.llms.deepseek import DeepseekLLMClient
    from dbgpt.model.proxy.llms.gemini import GeminiLLMClient
    from dbgpt.model.proxy.llms.gitee import GiteeLLMClient
    from dbgpt.model.proxy.llms.infiniai import InfiniAILLMClient
    from dbgpt.model.proxy.llms.moonshot import MoonshotLLMClient
    from dbgpt.model.proxy.llms.ollama import OllamaLLMClient
    from dbgpt.model.proxy.llms.siliconflow import SiliconFlowLLMClient
    from dbgpt.model.proxy.llms.spark import SparkLLMClient
    from dbgpt.model.proxy.llms.tongyi import TongyiLLMClient
    from dbgpt.model.proxy.llms.wenxin import WenxinLLMClient
    from dbgpt.model.proxy.llms.yi import YiLLMClient
    from dbgpt.model.proxy.llms.zhipu import ZhipuLLMClient


def __lazy_import(name):
    module_path = {
        "OpenAILLMClient": "dbgpt.model.proxy.llms.chatgpt",
        "BurnCloudLLMClient": "dbgpt.model.proxy.llms.burncloud",
        "ClaudeLLMClient": "dbgpt.model.proxy.llms.claude",
        "GeminiLLMClient": "dbgpt.model.proxy.llms.gemini",
        "AimlapiLLMClient": "dbgpt.model.proxy.llms.aimlapi",
        "SiliconFlowLLMClient": "dbgpt.model.proxy.llms.siliconflow",
        "SparkLLMClient": "dbgpt.model.proxy.llms.spark",
        "TongyiLLMClient": "dbgpt.model.proxy.llms.tongyi",
        "WenxinLLMClient": "dbgpt.model.proxy.llms.wenxin",
        "ZhipuLLMClient": "dbgpt.model.proxy.llms.zhipu",
        "YiLLMClient": "dbgpt.model.proxy.llms.yi",
        "MoonshotLLMClient": "dbgpt.model.proxy.llms.moonshot",
        "OllamaLLMClient": "dbgpt.model.proxy.llms.ollama",
        "DeepseekLLMClient": "dbgpt.model.proxy.llms.deepseek",
        "GiteeLLMClient": "dbgpt.model.proxy.llms.gitee",
        "InfiniAILLMClient": "dbgpt.model.proxy.llms.infiniai",
    }

    if name in module_path:
        module = __import__(module_path[name], fromlist=[name])
        return getattr(module, name)
    else:
        raise AttributeError(f"module {__name__} has no attribute {name}")


def __getattr__(name):
    return __lazy_import(name)


__all__ = [
    "OpenAILLMClient",
    "BurnCloudLLMClient",
    "ClaudeLLMClient",
    "GeminiLLMClient",
    "TongyiLLMClient",
    "ZhipuLLMClient",
    "WenxinLLMClient",
    "AimlapiLLMClient",
    "SiliconFlowLLMClient",
    "SparkLLMClient",
    "YiLLMClient",
    "MoonshotLLMClient",
    "OllamaLLMClient",
    "DeepseekLLMClient",
    "GiteeLLMClient",
    "InfiniAILLMClient",
]
