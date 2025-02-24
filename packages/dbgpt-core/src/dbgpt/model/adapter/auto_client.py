from dbgpt.core import LLMClient


class AutoLLMClient(LLMClient):
    def __init__(self, provider: str, name: str, **kwargs):
        from dbgpt.model import scan_model_providers
        from dbgpt.model.adapter.base import get_model_adapter
        from dbgpt.model.adapter.proxy_adapter import ProxyLLMModelAdapter

        scan_model_providers()

        kwargs["name"] = name
        adapter = get_model_adapter(provider, model_name=name)
        if not adapter:
            raise ValueError(
                f"Can not find adapter for model {name} and provider {provider}"
            )
        if not isinstance(adapter, ProxyLLMModelAdapter):
            raise ValueError(
                f"Now only support proxy model, but got {adapter.model_type()}"
            )
        param_cls = adapter.model_param_class()
        param = param_cls(**kwargs)
        model, _ = adapter.load_from_params(param)
        self._client_impl = model.proxy_llm_client

    def __getattr__(self, name: str):
        """Forward all attribute access to the client implementation."""
        if hasattr(self._client_impl, name):
            return getattr(self._client_impl, name)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def generate(self, *args, **kwargs):
        return self._client_impl.generate(*args, **kwargs)

    def generate_stream(self, *args, **kwargs):
        return self._client_impl.generate_stream(*args, **kwargs)

    def count_token(self, *args, **kwargs):
        return self._client_impl.count_token(*args, **kwargs)

    def models(self, *args, **kwargs):
        return self._client_impl.models(*args, **kwargs)
