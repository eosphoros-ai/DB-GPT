"""Ollama Embeddings."""

from dataclasses import dataclass, field
from typing import List, Optional, Type

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import EmbeddingModelMetadata, Embeddings
from dbgpt.core.interface.parameter import EmbeddingDeployModelParameters
from dbgpt.model.adapter.base import register_embedding_adapter
from dbgpt.util.i18n_utils import _


@dataclass
class OllamaEmbeddingDeployModelParameters(EmbeddingDeployModelParameters):
    """Ollama Embeddings deploy model parameters."""

    provider: str = "proxy/ollama"

    api_url: str = field(
        default="http://localhost:11434",
        metadata={
            "help": _("The URL of the embeddings API."),
        },
    )
    backend: Optional[str] = field(
        default=None,
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


class OllamaEmbeddings(BaseModel, Embeddings):
    """Ollama proxy embeddings.

    This class is used to get embeddings for a list of texts using the Ollama API.
    It requires a proxy server url `api_url` and a model name `model_name`.
    The default model name is "llama2".
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    api_url: str = Field(
        default="http://localhost:11434",
        description="The URL of the embeddings API.",
    )
    model_name: str = Field(
        default="llama2", description="The name of the model to use."
    )

    def __init__(self, **kwargs):
        """Initialize the OllamaEmbeddings."""
        super().__init__(**kwargs)

    @classmethod
    def param_class(cls) -> Type[OllamaEmbeddingDeployModelParameters]:
        """Get the parameter class."""
        return OllamaEmbeddingDeployModelParameters

    @classmethod
    def from_parameters(
        cls, parameters: OllamaEmbeddingDeployModelParameters
    ) -> "Embeddings":
        """Create an embedding model from parameters."""
        return cls(
            api_url=parameters.api_url, model_name=parameters.real_provider_model_name
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Get the embeddings for a list of texts.

        Args:
            texts (Documents): A list of texts to get embeddings for.

        Returns:
            Embedded texts as List[List[float]], where each inner List[float]
                corresponds to a single input text.
        """
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a OpenAPI embedding model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        try:
            import ollama
            from ollama import Client
        except ImportError as e:
            raise ValueError(
                "Could not import python package: ollama "
                "Please install ollama by command `pip install ollama"
            ) from e
        try:
            embedding = Client(self.api_url).embeddings(
                model=self.model_name, prompt=text
            )
            return list(embedding["embedding"])
        except ollama.ResponseError as e:
            raise ValueError(f"**Ollama Response Error, Please CheckErrorInfo.**: {e}")

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs.

        Args:
            texts: A list of texts to get embeddings for.

        Returns:
            List[List[float]]: Embedded texts as List[List[float]], where each inner
                List[float] corresponds to a single input text.
        """
        embeddings = []
        for text in texts:
            embedding = await self.aembed_query(text)
            embeddings.append(embedding)
        return embeddings

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        try:
            import ollama
            from ollama import AsyncClient
        except ImportError:
            raise ValueError(
                "The ollama python package is not installed. "
                "Please install it with `pip install ollama`"
            )
        try:
            embedding = await AsyncClient(host=self.api_url).embeddings(
                model=self.model_name, prompt=text
            )
            return list(embedding["embedding"])
        except ollama.ResponseError as e:
            raise ValueError(f"**Ollama Response Error, Please CheckErrorInfo.**: {e}")


register_embedding_adapter(
    OllamaEmbeddings,
    supported_models=[
        EmbeddingModelMetadata(
            model=["BAAI/bge-m3"],
            dimension=1024,
            context_length=8192,
            description=_(
                "The embedding model are trained by BAAI, it support more than 100 "
                "working languages."
            ),
            link="https://ollama.com/library/bge-m3",
        )
    ],
)
