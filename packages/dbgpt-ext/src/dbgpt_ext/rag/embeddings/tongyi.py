"""Tongyi embeddings for RAG."""

from dataclasses import dataclass, field
from typing import List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import EmbeddingModelMetadata, Embeddings
from dbgpt.core.interface.parameter import EmbeddingDeployModelParameters
from dbgpt.model.adapter.base import register_embedding_adapter
from dbgpt.util.i18n_utils import _


@dataclass
class TongyiEmbeddingDeployModelParameters(EmbeddingDeployModelParameters):
    """Qianfan Embeddings deploy model parameters."""

    provider: str = "proxy/tongyi"

    api_key: Optional[str] = field(
        default=None, metadata={"help": _("The API key for the embeddings API.")}
    )
    backend: Optional[str] = field(
        default="text-embedding-v1",
        metadata={
            "help": _(
                "The real model name to pass to the provider, default is None. If "
                "backend is None, use name as the real model name."
            ),
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.backend or self.name


class TongYiEmbeddings(BaseModel, Embeddings):
    """The tongyi embeddings.

    import dashscope
    from http import HTTPStatus
    from dashscope import TextEmbedding

    dashscope.api_key = ''
    def embed_with_list_of_str():
        resp = TextEmbedding.call(
            model=TextEmbedding.Models.text_embedding_v1,
            # 最多支持10条，每条最长支持2048tokens
            input=[
                '风急天高猿啸哀', '渚清沙白鸟飞回', '无边落木萧萧下', '不尽长江滚滚来'
            ]
        )
        if resp.status_code == HTTPStatus.OK:
            print(resp)
        else:
            print(resp)

    if __name__ == '__main__':
        embed_with_list_of_str()
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    api_key: Optional[str] = Field(
        default=None, description="The API key for the embeddings API."
    )
    model_name: str = Field(
        default="text-embedding-v1", description="The name of the model to use."
    )

    def __init__(self, **kwargs):
        """Initialize the OpenAPIEmbeddings."""
        try:
            import dashscope  # type: ignore
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: dashscope "
                "Please install dashscope by command `pip install dashscope"
            ) from exc
        dashscope.TextEmbedding.api_key = kwargs.get("api_key")
        super().__init__(**kwargs)
        self._api_key = kwargs.get("api_key")

    @classmethod
    def param_class(cls) -> Type[TongyiEmbeddingDeployModelParameters]:
        """Get the parameter class."""
        return TongyiEmbeddingDeployModelParameters

    @classmethod
    def from_parameters(
        cls, parameters: TongyiEmbeddingDeployModelParameters
    ) -> "Embeddings":
        """Create an embedding model from parameters."""
        return cls(
            api_key=parameters.api_key,
            model_name=parameters.real_provider_model_name,
        )

    def embed_documents(
        self, texts: List[str], max_batch_chunks_size=25
    ) -> List[List[float]]:
        """Get the embeddings for a list of texts.

        refer:https://help.aliyun.com/zh/model-studio/getting-started/models?
        spm=a2c4g.11186623.0.0.62524a77NlILDI#c05fe72732770

        Args:
            texts (Documents): A list of texts to get embeddings for.
            max_batch_chunks_size: The max batch size for embedding.

        Returns:
            Embedded texts as List[List[float]], where each inner List[float]
                corresponds to a single input text.
        """
        from dashscope import TextEmbedding

        embeddings = []
        # batch size too longer may cause embedding error,eg: qwen online embedding
        # models must not be larger than 25
        # text-embedding-v3  embedding batch size should not be larger than 6
        if str(self.model_name) == "text-embedding-v3":
            max_batch_chunks_size = 6

        for i in range(0, len(texts), max_batch_chunks_size):
            batch_texts = texts[i : i + max_batch_chunks_size]
            resp = TextEmbedding.call(
                model=self.model_name, input=batch_texts, api_key=self._api_key
            )
            if "output" not in resp:
                raise RuntimeError(resp["message"])

            # 提取并排序嵌入
            batch_embeddings = resp["output"]["embeddings"]
            sorted_embeddings = sorted(batch_embeddings, key=lambda e: e["text_index"])
            embeddings.extend([result["embedding"] for result in sorted_embeddings])

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a OpenAPI embedding model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        return self.embed_documents([text])[0]


register_embedding_adapter(
    TongYiEmbeddings,
    supported_models=[
        EmbeddingModelMetadata(
            model="text-embedding-v3",
            dimension=1024,
            context_length=8192,
            description=_(
                "The embedding model are trained by TongYi, it support more than 50 "
                "working languages."
            ),
        )
    ],
)
