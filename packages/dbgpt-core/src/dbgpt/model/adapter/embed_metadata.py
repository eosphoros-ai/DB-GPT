from typing import List

from dbgpt.core import EmbeddingModelMetadata
from dbgpt.util.i18n_utils import _

EMBED_COMMON_LLAMA_CPP_MODELS = []
EMBED_COMMON_HF_MODELS = []
RERANKER_COMMON_HF_MODELS = []


def _register_embed_common_hf_models(models: List[EmbeddingModelMetadata]) -> None:
    global EMBED_COMMON_HF_MODELS
    EMBED_COMMON_HF_MODELS.extend(models)


def _register_reranker_common_hf_models(models: List[EmbeddingModelMetadata]) -> None:
    global RERANKER_COMMON_HF_MODELS
    RERANKER_COMMON_HF_MODELS.extend(models)


EMBED_COMMON_HF_BGE_MODELS = [
    EmbeddingModelMetadata(
        model=["BAAI/bge-m3"],
        dimension=1024,
        context_length=8192,
        description=_(
            "The embedding model are trained by BAAI, it support more than 100 "
            "working languages."
        ),
        link="https://huggingface.co/BAAI/bge-m3",
    ),
    EmbeddingModelMetadata(
        model=["BAAI/bge-large-zh-v1.5"],
        dimension=1024,
        context_length=512,
        description=_("The embedding model are trained by BAAI, it support Chinese."),
        languages=["zh"],
        link="https://huggingface.co/BAAI/bge-large-zh-v1.5",
    ),
    EmbeddingModelMetadata(
        model=["BAAI/bge-large-en-v1.5"],
        dimension=1024,
        context_length=512,
        description=_("The embedding model are trained by BAAI, it support English."),
        languages=["en"],
        link="https://huggingface.co/BAAI/bge-large-en-v1.5",
    ),
]
EMBED_COMMON_HF_JINA_MODELS = [
    EmbeddingModelMetadata(
        model=["jinaai/jina-embeddings-v3"],
        context_length=8192,
        description=_(
            "The embedding model are trained by Jina AI, it support multiple "
            "languages. And it has 0.57B parameters."
        ),
        link="https://huggingface.co/jinaai/jina-embeddings-v3",
    ),
]

RERANKER_COMMON_HF_BGE_MODELS = [
    EmbeddingModelMetadata(
        model=["BAAI/bge-reranker-v2-m3"],
        description=_(
            "The reranker model are trained by BAAI, it support multiple languages."
        ),
        link="https://huggingface.co/BAAI/bge-reranker-v2-m3",
        is_reranker=True,
    ),
    EmbeddingModelMetadata(
        model=["BAAI/bge-reranker-large", "BAAI/bge-reranker-base"],
        description=_(
            "The reranker model are trained by BAAI, it support Chinese and English."
        ),
        link="https://huggingface.co/BAAI/bge-reranker-base",
        languages=["zh", "en"],
        is_reranker=True,
    ),
]
RERANKER_COMMON_HF_JINA_MODELS = [
    EmbeddingModelMetadata(
        model=["jinaai/jina-reranker-v2-base-multilingual"],
        context_length=1024,
        description=_(
            "The reranker model are trained by Jina AI, it support multiple languages."
        ),
        link="https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual",
        is_reranker=True,
    ),
]

_register_embed_common_hf_models(EMBED_COMMON_HF_BGE_MODELS)
_register_embed_common_hf_models(EMBED_COMMON_HF_JINA_MODELS)

# Register reranker models
_register_reranker_common_hf_models(RERANKER_COMMON_HF_BGE_MODELS)
_register_reranker_common_hf_models(RERANKER_COMMON_HF_JINA_MODELS)
