"""XM4 gateway using the OpenAI-compatible Chat Completions API."""

from concurrent.futures import Executor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from dbgpt.core import ModelMetadata, ModelRequest
from dbgpt.model.proxy.base import register_proxy_model_adapter

from .chatgpt import OpenAICompatibleDeployModelParameters, OpenAILLMClient

XM4_API_BASE = "https://xm4.meitnru.site:8443/v1"

# Limits and reasoning variants supplied by the gateway configuration.
_STANDARD_VARIANTS = ["low", "medium", "high", "xhigh"]
_EXTENDED_VARIANTS = [*_STANDARD_VARIANTS, "max"]
_MODEL_SPECS = [
    ("gpt-6", "GPT-6 (Astra)", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-6-astra", "GPT-6 Astra", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-5.2", "GPT-5.2", 400_000, 128_000, _STANDARD_VARIANTS),
    ("gpt-5.6", "GPT-5.6 (Sol)", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-6-sol", "GPT-6 Sol", 1_050_000, 128_000, ["none", *_EXTENDED_VARIANTS]),
    ("gpt-5.6-sol", "GPT-5.6 Sol", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-5.6-terra", "GPT-5.6 Terra", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-6-luna", "GPT-6 Luna", 1_050_000, 128_000, ["none", *_EXTENDED_VARIANTS]),
    ("gpt-5.6-luna", "GPT-5.6 Luna", 1_050_000, 128_000, _EXTENDED_VARIANTS),
    ("gpt-5.5", "GPT-5.5", 1_050_000, 128_000, _STANDARD_VARIANTS),
    ("gpt-5.4", "GPT-5.4", 1_050_000, 128_000, _STANDARD_VARIANTS),
    ("gpt-5.4-mini", "GPT-5.4 Mini", 400_000, 128_000, _STANDARD_VARIANTS),
    ("gpt-5.3-codex-spark", "GPT-5.3 Codex Spark", 128_000, 32_000, _STANDARD_VARIANTS),
    ("codex-mini-latest", "Codex Mini", 200_000, 100_000, ["low", "medium", "high"]),
]
XM4_MODELS = [
    ModelMetadata(
        model=model,
        label=label,
        context_length=context,
        max_output_length=output,
        function_calling=True,
        metadata={"reasoning_variants": variants, "store": False},
    )
    for model, label, context, output, variants in _MODEL_SPECS
]
_MODELS_BY_NAME = {model.model: model for model in XM4_MODELS}


async def list_xm4_models(api_key: str, api_base: Optional[str]) -> List[ModelMetadata]:
    """Discover models authorized for the key's gateway group."""
    import httpx

    base = Xm4LLMClient._resolve_env_vars(api_base) or XM4_API_BASE
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{base.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        entries = response.json()["data"]
    models = {}
    for entry in entries:
        name = entry["id"]
        models[name] = _MODELS_BY_NAME.get(name) or ModelMetadata(
            model=name,
            label=name,
            context_length=None,
            max_output_length=None,
            function_calling=None,
        )
    return list(models.values())


@dataclass
class Xm4DeployModelParameters(OpenAICompatibleDeployModelParameters):
    """Deploy parameters for the XM4 OpenAI-compatible gateway."""

    provider: str = "proxy/xm4"
    api_base: Optional[str] = field(
        default=f"${{env:XM4_API_BASE:-{XM4_API_BASE}}}",
        metadata={"help": "The base URL of the XM4 gateway."},
    )
    api_key: Optional[str] = field(
        default="${env:XM4_API_KEY}",
        metadata={"help": "The API key of the XM4 gateway.", "tags": "privacy"},
    )
    reasoning_effort: Optional[str] = field(
        default=None,
        metadata={
            "help": "Optional reasoning variant supported by the selected model."
        },
    )


class Xm4LLMClient(OpenAILLMClient):
    """Reuse OpenAI transport with gateway-specific request defaults."""

    @classmethod
    def param_class(cls) -> Type[Xm4DeployModelParameters]:
        return Xm4DeployModelParameters

    @classmethod
    def new_client(
        cls,
        model_params: Xm4DeployModelParameters,
        default_executor: Optional[Executor] = None,
    ) -> "Xm4LLMClient":
        model = model_params.real_provider_model_name
        spec = _MODELS_BY_NAME.get(model)
        effort = model_params.reasoning_effort
        if effort and (not spec or effort not in spec.metadata["reasoning_variants"]):
            raise ValueError(
                f"Unsupported XM4 reasoning variant {effort!r} for {model}"
            )
        return cls(
            api_key=model_params.api_key,
            api_base=model_params.api_base,
            model=model,
            model_alias=model,
            proxy=model_params.http_proxy,
            context_length=model_params.context_length
            or (spec.context_length if spec else 8192),
            openai_kwargs={"reasoning_effort": effort} if effort else None,
        )

    def _build_request(
        self, request: ModelRequest, stream: Optional[bool] = False
    ) -> Dict[str, Any]:
        payload = super()._build_request(request, stream)
        payload["store"] = False
        if payload["model"] not in _MODELS_BY_NAME:
            # Domestic models retain OpenAI-compatible sampling/token parameters.
            if payload["model"].startswith(("deepseek-", "glm-")):
                # Flash defaults must leave the output budget for executable
                # tool arguments instead of consuming it all in reasoning.
                payload["extra_body"] = {
                    **payload.get("extra_body", {}),
                    "thinking": {"type": "disabled"},
                }
            return payload
        # GPT reasoning models use the completion budget for reasoning + output.
        budget = payload.pop("max_tokens", None)
        if budget is not None:
            spec = _MODELS_BY_NAME.get(payload["model"])
            payload["max_completion_tokens"] = (
                min(budget, spec.max_output_length) if spec else budget
            )
        # These models use their default sampling settings.
        payload.pop("temperature", None)
        payload.pop("top_p", None)
        return payload


register_proxy_model_adapter(Xm4LLMClient, supported_models=XM4_MODELS)
