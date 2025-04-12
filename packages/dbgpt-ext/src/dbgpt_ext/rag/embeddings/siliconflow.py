from dataclasses import dataclass, field
from typing import List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import EmbeddingModelMetadata, Embeddings
from dbgpt.core.interface.parameter import EmbeddingDeployModelParameters
from dbgpt.model.adapter.base import register_embedding_adapter
from dbgpt.util.i18n_utils import _


@dataclass
class SiliconFlowEmbeddingDeployModelParameters(EmbeddingDeployModelParameters):
    """SiliconFlow Embeddings deploy model parameters."""

    provider: str = "proxy/siliconflow"

    api_key: Optional[str] = field(
        default="${env:SILICONFLOW_API_KEY}",
        metadata={
            "help": _("The API key for the rerank API."),
        },
    )
    backend: Optional[str] = field(
        default="BAAI/bge-m3",
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


class SiliconFlowEmbeddings(BaseModel, Embeddings):
    """The SiliconFlow embeddings."""

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    api_key: Optional[str] = Field(
        default=None, description="The API key for the embeddings API."
    )
    model_name: str = Field(
        default="BAAI/bge-m3", description="The name of the model to use."
    )

    def __init__(self, **kwargs):
        """Initialize the SiliconFlow Embeddings."""
        super().__init__(**kwargs)
        self._api_key = self.api_key

    @classmethod
    def param_class(cls) -> Type[SiliconFlowEmbeddingDeployModelParameters]:
        """Get the parameter class."""
        return SiliconFlowEmbeddingDeployModelParameters

    @classmethod
    def from_parameters(
        cls, parameters: SiliconFlowEmbeddingDeployModelParameters
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

        Args:
            texts (List[str]): A list of texts to get embeddings for.
            max_batch_chunks_size: The max batch size for embedding.

        Returns:
            Embedded texts as List[List[float]], where each inner List[float]
                corresponds to a single input text.
        """
        import requests

        embeddings = []
        headers = {"Authorization": f"Bearer {self._api_key}"}

        for i in range(0, len(texts), max_batch_chunks_size):
            batch_texts = texts[i : i + max_batch_chunks_size]
            response = requests.post(
                url="https://api.siliconflow.cn/v1/embeddings",
                json={"model": self.model_name, "input": batch_texts},
                headers=headers,
            )

            if response.status_code != 200:
                raise RuntimeError(f"Embedding failed: {response.text}")

            # 提取并排序嵌入
            data = response.json()
            batch_embeddings = data["data"]
            sorted_embeddings = sorted(batch_embeddings, key=lambda e: e["index"])
            embeddings.extend([result["embedding"] for result in sorted_embeddings])

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a SiliconFlow embedding model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        return self.embed_documents([text])[0]


register_embedding_adapter(
    SiliconFlowEmbeddings,
    supported_models=[
        EmbeddingModelMetadata(
            model="BAAI/bge-m3",
            dimension=1024,
            context_length=8192,
            description=_(
                "The embedding model is provided by SiliconFlow, supporting multiple "
                "languages and high-quality text embeddings."
            ),
        ),
        EmbeddingModelMetadata(
            model="BAAI/bge-large-zh-v1.5",
            dimension=1024,
            context_length=512,
            description=_(
                "The embedding model is provided by SiliconFlow, supporting multiple "
                "languages and high-quality text embeddings."
            ),
        ),
        EmbeddingModelMetadata(
            model="BAAI/bge-large-en-v1.5",
            dimension=1024,
            context_length=512,
            description=_(
                "The embedding model is provided by SiliconFlow, supporting multiple "
                "languages and high-quality text embeddings."
            ),
        ),
    ],
)
