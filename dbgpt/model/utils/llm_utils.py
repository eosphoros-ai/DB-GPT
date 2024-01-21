#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from pathlib import Path
from typing import Dict, List

import cachetools

from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG, LLM_MODEL_CONFIG
from dbgpt.model.base import SupportedModel
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


@cachetools.cached(cachetools.TTLCache(maxsize=100, ttl=60 * 5))
def list_supported_models():
    from dbgpt.model.parameter import WorkerType

    models = _list_supported_models(WorkerType.LLM.value, LLM_MODEL_CONFIG)
    models += _list_supported_models(WorkerType.TEXT2VEC.value, EMBEDDING_MODEL_CONFIG)
    return models


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
