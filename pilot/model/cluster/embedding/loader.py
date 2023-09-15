from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.model.parameter import BaseEmbeddingModelParameters

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings


class EmbeddingLoader:
    def __init__(self) -> None:
        pass

    def load(
        self, model_name: str, param: BaseEmbeddingModelParameters
    ) -> "Embeddings":
        # add more models
        if model_name in ["proxy_openai", "proxy_azure"]:
            from langchain.embeddings import OpenAIEmbeddings

            return OpenAIEmbeddings(**param.build_kwargs())
        else:
            from langchain.embeddings import HuggingFaceEmbeddings

            kwargs = param.build_kwargs(model_name=param.model_path)
            return HuggingFaceEmbeddings(**kwargs)
