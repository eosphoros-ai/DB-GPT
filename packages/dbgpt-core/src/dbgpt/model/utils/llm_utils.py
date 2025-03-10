from pathlib import Path
from typing import Any, Dict, List

import cachetools

from dbgpt.core import ModelRequest, ModelRequestContext
from dbgpt.model.base import SupportedModel
from dbgpt.util.annotations import Deprecated
from dbgpt.util.parameter_utils import _get_parameter_descriptions


def is_sentence_complete(output: str):
    """Check whether the output is a complete sentence."""
    end_symbols = (".", "?", "!", "...", "。", "？", "！", "…", '"', "'", "”")
    return output.endswith(end_symbols)


def is_partial_stop(output: str, stop_str: str):
    """Check whether the output contains a partial stop str."""
    for i in range(0, min(len(output), len(stop_str))):
        if stop_str.startswith(output[-i:]):
            return True
    return False


@cachetools.cached(cachetools.TTLCache(maxsize=100, ttl=10))
def list_supported_models():
    from dbgpt.model.adapter.base import get_supported_models
    from dbgpt.model.parameter import WorkerType

    models = get_supported_models(WorkerType.LLM.value)
    models += get_supported_models(WorkerType.TEXT2VEC.value)
    models += get_supported_models(WorkerType.RERANKER.value)
    return models


def _list_supported_models_from_adapter(worker_type: str) -> List[SupportedModel]:
    pass


@Deprecated(version="0.7.0", remove_version="0.8.8")
def _list_supported_models(
    worker_type: str, model_config: Dict[str, str]
) -> List[SupportedModel]:
    from dbgpt.model.adapter.loader import _get_model_real_path
    from dbgpt.model.adapter.model_adapter import get_llm_model_adapter

    ret = []
    for model_name, model_path in model_config.items():
        model_path = _get_model_real_path(model_name, model_path)
        model = SupportedModel(
            model=model_name,
            path=model_path,
            worker_type=worker_type,
            path_exist=False,
            proxy=False,
            enabled=False,
            params=None,
        )
        if "proxyllm" in model_name:
            model.proxy = True
        else:
            path = Path(model_path)
            model.path_exist = path.exists()
        param_cls = None
        try:
            llm_adapter = get_llm_model_adapter(model_name, model_path)
            param_cls = llm_adapter.model_param_class()
            model.enabled = True
            params = _get_parameter_descriptions(
                param_cls, model_name=model_name, model_path=model_path
            )
            model.params = params
        except Exception:
            pass
        ret.append(model)
    return ret


def parse_model_request(
    params: Dict[str, Any], default_model: str, stream: bool = True
) -> ModelRequest:
    """Parse model request from params.

    Args:
        params (Dict[str, Any]): request params
        default_model (str): default model name
        stream (bool, optional): whether stream. Defaults to True.
    """
    context = ModelRequestContext(
        stream=stream,
        user_name=params.get("user_name"),
        request_id=params.get("request_id"),
        is_reasoning_model=params.get("is_reasoning_model", False),
    )
    request = ModelRequest.build_request(
        default_model,
        messages=params["messages"],
        temperature=params.get("temperature"),
        context=context,
        max_new_tokens=params.get("max_new_tokens"),
        stop=params.get("stop"),
        top_p=params.get("top_p"),
    )
    return request
