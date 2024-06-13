"""Re-rank embeddings."""

from typing import Any, Dict, List, Optional, cast

import aiohttp
import numpy as np
import requests

from dbgpt._private.pydantic import EXTRA_FORBID, BaseModel, ConfigDict, Field
from dbgpt.core import RerankEmbeddings


class CrossEncoderRerankEmbeddings(BaseModel, RerankEmbeddings):
    """CrossEncoder Rerank Embeddings."""

    model_config = ConfigDict(extra=EXTRA_FORBID, protected_namespaces=())

    client: Any  #: :meta private:
    model_name: str = "BAAI/bge-reranker-base"
    max_length: int = None  # type: ignore
    """Max length for input sequences. Longer sequences will be truncated. If None, max
        length of the model will be used"""
    """Model name to use."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Keyword arguments to pass to the model."""

    def __init__(self, **kwargs: Any):
        """Initialize the sentence_transformer."""
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise ImportError(
                "please `pip install sentence-transformers`",
            )

        kwargs["client"] = CrossEncoder(
            kwargs.get("model_name", "BAAI/bge-reranker-base"),
            max_length=kwargs.get("max_length"),  # type: ignore
            **(kwargs.get("model_kwargs") or {}),
        )
        super().__init__(**kwargs)

    def predict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the rank scores of the candidates.

        Args:
            query: The query text.
            candidates: The list of candidate texts.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        from sentence_transformers import CrossEncoder

        query_content_pairs = [[query, candidate] for candidate in candidates]
        _model = cast(CrossEncoder, self.client)
        rank_scores = _model.predict(sentences=query_content_pairs)
        if isinstance(rank_scores, np.ndarray):
            rank_scores = rank_scores.tolist()
        return rank_scores  # type: ignore


class OpenAPIRerankEmbeddings(BaseModel, RerankEmbeddings):
    """OpenAPI Rerank Embeddings."""

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    api_url: str = Field(
        default="http://localhost:8100/v1/beta/relevance",
        description="The URL of the embeddings API.",
    )
    api_key: Optional[str] = Field(
        default=None, description="The API key for the embeddings API."
    )
    model_name: str = Field(
        default="bge-reranker-base", description="The name of the model to use."
    )
    timeout: int = Field(
        default=60, description="The timeout for the request in seconds."
    )

    session: Optional[requests.Session] = None

    def __init__(self, **kwargs):
        """Initialize the OpenAPIEmbeddings."""
        try:
            import requests
        except ImportError:
            raise ValueError(
                "The requests python package is not installed. "
                "Please install it with `pip install requests`"
            )
        if "session" not in kwargs:  # noqa: SIM401
            session = requests.Session()
        else:
            session = kwargs["session"]
        api_key = kwargs.get("api_key")
        if api_key:
            session.headers.update({"Authorization": f"Bearer {api_key}"})
        kwargs["session"] = session
        super().__init__(**kwargs)

    def predict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the rank scores of the candidates.

        Args:
            query: The query text.
            candidates: The list of candidate texts.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        if not candidates:
            return []
        data = {"model": self.model_name, "query": query, "documents": candidates}
        response = self.session.post(  # type: ignore
            self.api_url, json=data, timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()["data"]

    async def apredict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the rank scores of the candidates asynchronously."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            data = {"model": self.model_name, "query": query, "documents": candidates}
            async with session.post(self.api_url, json=data) as resp:
                resp.raise_for_status()
                response_data = await resp.json()
                if "data" not in response_data:
                    raise RuntimeError(response_data["detail"])
                return response_data["data"]
