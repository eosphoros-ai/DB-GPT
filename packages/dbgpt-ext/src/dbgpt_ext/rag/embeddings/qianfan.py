"""Qianfan Embeddings module."""

from typing import Any, Optional, Dict, List

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import Embeddings


class QianFanEmbeddings(BaseModel, Embeddings):
    """Baidu Qianfan Embeddings embedding models.

    Embed:
       .. code-block:: python

           # embed the documents
           vectors = embeddings.embed_documents([text1, text2, ...])

           # embed the query
           vectors = embeddings.embed_query(text)

    """  # noqa: E501

    client: Any
    chunk_size: int = 16
    endpoint: str = ""
    """Endpoint of the Qianfan Embedding, required if custom model used."""
    model_config = ConfigDict(arbitrary_types_allowed=True, protected_namespaces=())
    api_key: Optional[str] = Field(
        default=None, description="The API key for the embeddings API."
    )
    api_secret: Optional[str] = Field(
        default=None, description="The Secret key for the embeddings API."
    )
    """Model name
    you could get from https://cloud.baidu.com/doc/WENXINWORKSHOP/s/Nlks5zkzu

    for now, we support Embedding-V1 and
    - Embedding-V1 （默认模型）
    - bge-large-en
    - bge-large-zh

    preset models are mapping to an endpoint.
    `model` will be ignored if `endpoint` is set
    """
    model_name: str = Field(
        default="text-embedding-v1", description="The name of the model to use."
    )
    init_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """init kwargs for qianfan client init, such as `query_per_second` which is
        associated with qianfan resource object to limit QPS"""

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """extra params for model invoke using with `do`."""

    def __init__(self, **kwargs):
        """Initialize the QianFanEmbeddings."""
        try:
            import qianfan
        except ImportError as exc:
            raise ValueError(
                "Could not import python package: qianfan. "
                "Please install qianfan by running `pip install qianfan`."
            ) from exc

        qianfan_ak = kwargs.get("api_key")
        qianfan_sk = kwargs.get("api_secret")
        model_name = kwargs.get("model_name")

        if not qianfan_ak or not qianfan_sk or not model_name:
            raise ValueError(
                "API key, API secret, and model name are required to initialize "
                "QianFanEmbeddings."
            )

        params = {
            "model": model_name,
            "ak": qianfan_ak,
            "sk": qianfan_sk,
        }

        # Initialize the qianfan.Embedding client
        kwargs["client"] = qianfan.Embedding(**params)
        super().__init__(**kwargs)

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a QianFan embedding model."""
        resp = self.embed_documents([text])
        return resp[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a list of text documents using the AutoVOT algorithm.

        Args:
            texts (List[str]): A list of text documents to embed.

        Returns:
            List[List[float]]: A list of embeddings for each document in the input list.
                            Each embedding is represented as a list of float values.
        """
        text_in_chunks = [
            texts[i : i + self.chunk_size]
            for i in range(0, len(texts), self.chunk_size)
        ]
        lst = []
        for chunk in text_in_chunks:
            resp = self.client.do(texts=chunk, **self.model_kwargs)
            lst.extend([res["embedding"] for res in resp["data"]])
        return lst
