"""Jina Embeddings module."""

from typing import Any, List

from dbgpt._private.pydantic import BaseModel, ConfigDict
from dbgpt.core import Embeddings
from dbgpt.rag.embedding.embeddings import _handle_request_result


class JinaEmbeddings(BaseModel, Embeddings):
    """Jina AI embeddings.

    This class is used to get embeddings for a list of texts using the Jina AI API.
    It requires an API key and a model name. The default model name is
    "jina-embeddings-v2-base-en".
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())

    api_url: Any  #: :meta private:
    session: Any  #: :meta private:
    api_key: str
    """API key for the Jina AI API.."""
    model_name: str = "jina-embeddings-v2-base-en"
    """The name of the model to use for text embeddings. Defaults to
    "jina-embeddings-v2-base-en"."""

    def __init__(self, **kwargs):
        """Create a new JinaEmbeddings instance."""
        try:
            import requests
        except ImportError:
            raise ValueError(
                "The requests python package is not installed. Please install it with "
                "`pip install requests`"
            )
        if "api_url" not in kwargs:
            kwargs["api_url"] = "https://api.jina.ai/v1/embeddings"
        if "session" not in kwargs:  # noqa: SIM401
            session = requests.Session()
        else:
            session = kwargs["session"]
        api_key = kwargs.get("api_key")
        if api_key:
            session.headers.update(
                {
                    "Authorization": f"Bearer {api_key}",
                    "Accept-Encoding": "identity",
                }
            )
        kwargs["session"] = session

        super().__init__(**kwargs)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Get the embeddings for a list of texts.

        Args:
            texts (Documents): A list of texts to get embeddings for.

        Returns:
            Embedded texts as List[List[float]], where each inner List[float]
                corresponds to a single input text.
        """
        # Call Jina AI Embedding API
        resp = self.session.post(  # type: ignore
            self.api_url, json={"input": texts, "model": self.model_name}
        )
        return _handle_request_result(resp)

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a Jina AI embedding model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        return self.embed_documents([text])[0]
