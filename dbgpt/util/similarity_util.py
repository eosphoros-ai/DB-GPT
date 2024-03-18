"""Utility functions for calculating similarity."""
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from dbgpt.core.interface.embeddings import Embeddings


def calculate_cosine_similarity(
    embeddings: "Embeddings", prediction: str, contexts: Sequence[str]
) -> Any:
    """Calculate the cosine similarity between a prediction and a list of contexts.

    Args:
        embeddings(Embeddings): The embeddings to use.
        prediction(str): The prediction.
        contexts(Sequence[str]): The contexts.

    Returns:
        numpy.ndarray: The cosine similarity.
    """
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for SimilarityMetric")
    prediction_vec = np.asarray(embeddings.embed_query(prediction)).reshape(1, -1)
    context_list = list(contexts)
    context_list_vec = np.asarray(embeddings.embed_documents(context_list)).reshape(
        len(contexts), -1
    )
    # cos(a,b) = dot(a,b) / (norm(a) * norm(b))
    dot = np.dot(context_list_vec, prediction_vec.T).reshape(
        -1,
    )
    norm = np.linalg.norm(context_list_vec, axis=1) * np.linalg.norm(
        prediction_vec, axis=1
    )
    return dot / norm
