"""Proxy models."""


def __lazy_import(name):
    module_path = {
        "OpenAILLMClient": "dbgpt.model.proxy.llms.chatgpt",
        "GeminiLLMClient": "dbgpt.model.proxy.llms.gemini",
        "SparkLLMClient": "dbgpt.model.proxy.llms.spark",
        "TongyiLLMClient": "dbgpt.model.proxy.llms.tongyi",
        "WenxinLLMClient": "dbgpt.model.proxy.llms.wenxin",
        "ZhipuLLMClient": "dbgpt.model.proxy.llms.zhipu",
        "YiLLMClient": "dbgpt.model.proxy.llms.yi",
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
    "GeminiLLMClient",
    "TongyiLLMClient",
    "ZhipuLLMClient",
    "WenxinLLMClient",
    "SparkLLMClient",
    "YiLLMClient",
]
