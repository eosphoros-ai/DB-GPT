"""Module for embedding related classes and functions."""

from .embedding_factory import (  # noqa: F401
    DefaultEmbeddingFactory,
    EmbeddingFactory,
    WrappedEmbeddingFactory,
)
from .embeddings import (  # noqa: F401
    Embeddings,
    HuggingFaceBgeEmbeddings,
    HuggingFaceEmbeddings,
    HuggingFaceInferenceAPIEmbeddings,
    HuggingFaceInstructEmbeddings,
    JinaEmbeddings,
    OllamaEmbeddings,
    OpenAPIEmbeddings,
)
from .rerank import CrossEncoderRerankEmbeddings, OpenAPIRerankEmbeddings  # noqa: F401

__ALL__ = [
    "Embeddings",
    "HuggingFaceBgeEmbeddings",
    "HuggingFaceEmbeddings",
    "HuggingFaceInferenceAPIEmbeddings",
    "HuggingFaceInstructEmbeddings",
    "JinaEmbeddings",
    "OpenAPIEmbeddings",
    "OllamaEmbeddings",
    "DefaultEmbeddingFactory",
    "EmbeddingFactory",
    "WrappedEmbeddingFactory",
    "CrossEncoderRerankEmbeddings",
    "OpenAPIRerankEmbeddings",
]
