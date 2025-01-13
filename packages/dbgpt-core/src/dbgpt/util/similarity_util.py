"""Utility functions for calculating similarity."""

from typing import TYPE_CHECKING, Any, List, Sequence

if TYPE_CHECKING:
    from dbgpt.core.interface.embeddings import Embeddings


def cosine_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """Calculate the cosine similarity between two vectors.

    Args:
        embedding1(List[float]): The first vector.
        embedding2(List[float]): The second vector.

    Returns:
        float: The cosine similarity.
    """
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for SimilarityMetric")
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    similarity = dot_product / (norm1 * norm2)
    return similarity


def sigmoid_function(x: float) -> float:
    """Calculate the sigmoid function.

    The sigmoid function is defined as:
    .. math::
        f(x) = \\frac{1}{1 + e^{-x}}

    It is used to map the input to a value between 0 and 1.

    Args:
        x(float): The input to the sigmoid function.

    Returns:
        float: The output of the sigmoid function.
    """
    try:
        import numpy as np
    except ImportError:
        raise ImportError("numpy is required for sigmoid_function")
    return 1 / (1 + np.exp(-x))


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
