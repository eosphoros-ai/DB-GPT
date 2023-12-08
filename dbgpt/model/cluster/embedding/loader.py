from __future__ import annotations

from typing import TYPE_CHECKING

from dbgpt.model.parameter import BaseEmbeddingModelParameters
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.tracer import root_tracer, SpanType, SpanTypeRunName
from dbgpt.util.system_utils import get_system_info

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


class EmbeddingLoader:
    def __init__(self) -> None:
        pass

    def load(
        self, model_name: str, param: BaseEmbeddingModelParameters
    ) -> "Embeddings":
        metadata = {
            "model_name": model_name,
            "run_service": SpanTypeRunName.EMBEDDING_MODEL.value,
            "params": _get_dict_from_obj(param),
            "sys_infos": _get_dict_from_obj(get_system_info()),
        }
        with root_tracer.start_span(
            "EmbeddingLoader.load", span_type=SpanType.RUN, metadata=metadata
        ):
            # add more models
            if model_name in ["proxy_openai", "proxy_azure"]:
                from langchain.embeddings import OpenAIEmbeddings

                return OpenAIEmbeddings(**param.build_kwargs())
            else:
                from langchain.embeddings import HuggingFaceEmbeddings

                kwargs = param.build_kwargs(model_name=param.model_path)
                return HuggingFaceEmbeddings(**kwargs)
