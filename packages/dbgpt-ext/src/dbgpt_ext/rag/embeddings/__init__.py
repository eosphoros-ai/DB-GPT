"""Module for embedding related classes and functions."""

from .embeddings.jina import (  # noqa: F401
    JinaEmbeddings,
    OllamaEmbeddings,
    OpenAPIEmbeddings,
    QianFanEmbeddings,
    TongYiEmbeddings,
)
from .rerank import (  # noqa: F401
    CrossEncoderRerankEmbeddings,
    OpenAPIRerankEmbeddings,
    SiliconFlowRerankEmbeddings,
)

__ALL__ = [
    "CrossEncoderRerankEmbeddings",
    "DefaultEmbeddingFactory",
    "EmbeddingFactory",
    "Embeddings",
    "HuggingFaceBgeEmbeddings",
    "HuggingFaceEmbeddings",
    "HuggingFaceInferenceAPIEmbeddings",
    "HuggingFaceInstructEmbeddings",
    "JinaEmbeddings",
    "OllamaEmbeddings",
    "OpenAPIEmbeddings",
    "OpenAPIRerankEmbeddings",
    "SiliconFlowRerankEmbeddings",
    "QianFanEmbeddings",
    "TongYiEmbeddings",
    "WrappedEmbeddingFactory",
]

