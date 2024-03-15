from __future__ import annotations

from typing import TYPE_CHECKING, Union, cast

from dbgpt.model.parameter import BaseEmbeddingModelParameters, ProxyEmbeddingParameters
from dbgpt.util.parameter_utils import _get_dict_from_obj
from dbgpt.util.system_utils import get_system_info
from dbgpt.util.tracer import SpanType, SpanTypeRunName, root_tracer

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings as LangChainEmbeddings

    from dbgpt.rag.embedding import Embeddings, HuggingFaceEmbeddings


class EmbeddingLoader:
    def __init__(self) -> None:
        pass

    def load(
        self, model_name: str, param: BaseEmbeddingModelParameters
    ) -> "Union[LangChainEmbeddings, Embeddings]":
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
            elif model_name in ["proxy_http_openapi"]:
                from dbgpt.rag.embedding import OpenAPIEmbeddings

                proxy_param = cast(ProxyEmbeddingParameters, param)
                openapi_param = {}
                if proxy_param.proxy_server_url:
                    openapi_param["api_url"] = proxy_param.proxy_server_url
                if proxy_param.proxy_api_key:
                    openapi_param["api_key"] = proxy_param.proxy_api_key
                if proxy_param.proxy_backend:
                    openapi_param["model_name"] = proxy_param.proxy_backend
                return OpenAPIEmbeddings(**openapi_param)
            else:
                from dbgpt.rag.embedding import HuggingFaceEmbeddings

                kwargs = param.build_kwargs(model_name=param.model_path)
                return HuggingFaceEmbeddings(**kwargs)
