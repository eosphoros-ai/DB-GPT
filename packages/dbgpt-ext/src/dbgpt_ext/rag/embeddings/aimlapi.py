"""AI/ML API embeddings for RAG."""

from dataclasses import dataclass, field
from typing import List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import EmbeddingModelMetadata, Embeddings
from dbgpt.core.interface.parameter import EmbeddingDeployModelParameters
from dbgpt.model.adapter.base import register_embedding_adapter
from dbgpt.util.i18n_utils import _

AIMLAPI_HEADERS = {
    "HTTP-Referer": "https://github.com/eosphoros-ai/DB-GPT",
    "X-Title": "DB GPT",
}


@dataclass
class AimlapiEmbeddingDeployModelParameters(EmbeddingDeployModelParameters):
    """AI/ML API Embeddings deploy model parameters."""

    provider: str = "proxy/aimlapi"

    api_key: Optional[str] = field(
        default="${env:AIMLAPI_API_KEY}",
        metadata={"help": _("The API key for the embeddings API.")},
    )
    backend: Optional[str] = field(
        default="text-embedding-3-small",
        metadata={
            "help": _(
                "The real model name to pass to the provider, default is None. If "
                "backend is None, use name as the real model name."
            ),
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        return self.backend or self.name


class AimlapiEmbeddings(BaseModel, Embeddings):
    """The AI/ML API embeddings."""

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    api_key: Optional[str] = Field(
        default=None, description="The API key for the embeddings API."
    )
    model_name: str = Field(
        default="text-embedding-3-small", description="The name of the model to use."
    )

    def __init__(self, **kwargs):
        """Initialize the AI/ML API Embeddings."""
        super().__init__(**kwargs)
        self._api_key = self.api_key

    @classmethod
    def param_class(cls) -> Type[AimlapiEmbeddingDeployModelParameters]:
        return AimlapiEmbeddingDeployModelParameters

    @classmethod
    def from_parameters(
        cls, parameters: AimlapiEmbeddingDeployModelParameters
    ) -> "Embeddings":
        return cls(
            api_key=parameters.api_key, model_name=parameters.real_provider_model_name
        )

    def embed_documents(
        self, texts: List[str], max_batch_chunks_size: int = 25
    ) -> List[List[float]]:
        """Get the embeddings for a list of texts."""
        import requests

        embeddings = []
        headers = {"Authorization": f"Bearer {self._api_key}"}
        headers.update(AIMLAPI_HEADERS)

        for i in range(0, len(texts), max_batch_chunks_size):
            batch_texts = texts[i : i + max_batch_chunks_size]
            response = requests.post(
                url="https://api.aimlapi.com/v1/embeddings",
                json={"model": self.model_name, "input": batch_texts},
                headers=headers,
            )
            if response.status_code != 200:
                raise RuntimeError(f"Embedding failed: {response.text}")
            data = response.json()
            batch_embeddings = data["data"]
            sorted_embeddings = sorted(batch_embeddings, key=lambda e: e["index"])
            embeddings.extend([result["embedding"] for result in sorted_embeddings])

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


register_embedding_adapter(
    AimlapiEmbeddings,
    supported_models=[
        EmbeddingModelMetadata(
            model=["text-embedding-3-large", "text-embedding-ada-002"],
            dimension=1536,
            context_length=8000,
            description=_(
                "High‑performance embedding models with "
                "flexible dimensions and superior accuracy."
            ),
            link="https://aimlapi.com/models",
        ),
        EmbeddingModelMetadata(
            model=["BAAI/bge-base-en-v1.5", "BAAI/bge-large-en-v1.5"],
            dimension=1536,
            context_length=None,
            description=_(
                "BAAI BGE models for precise and high‑performance language embeddings."
            ),
            link="https://aimlapi.com/models",
        ),
        EmbeddingModelMetadata(
            model=[
                "togethercomputer/m2-bert-80M-32k-retrieval",
                "voyage-finance-2",
                "voyage-multilingual-2",
            ],
            dimension=1536,
            context_length=32000,
            description=_(
                "High‑capacity embedding models with 32k token "
                "context window for retrieval and specialized domains."
            ),
            link="https://aimlapi.com/models",
        ),
        EmbeddingModelMetadata(
            model=[
                "voyage-large-2-instruct",
                "voyage-law-2",
                "voyage-code-2",
                "voyage-large-2",
            ],
            dimension=1536,
            context_length=16000,
            description=_(
                "Voyage embedding models with 16k token context window, "
                "optimized for general and instruction tasks."
            ),
            link="https://aimlapi.com/models",
        ),
        EmbeddingModelMetadata(
            model=["voyage-2"],
            dimension=1536,
            context_length=4000,
            description=_("Voyage 2: compact embeddings for smaller contexts."),
            link="https://aimlapi.com/models",
        ),
        EmbeddingModelMetadata(
            model=[
                "textembedding-gecko@003",
                "textembedding-gecko-multilingual@001",
                "text-multilingual-embedding-002",
            ],
            dimension=1536,
            context_length=2000,
            description=_(
                "Gecko and multilingual embedding models with 2k token context window."
            ),
            link="https://aimlapi.com/models",
        ),
    ],
)
