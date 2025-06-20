"""Re-rank embeddings."""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, cast

import aiohttp
import numpy as np
import requests

from dbgpt._private.pydantic import EXTRA_FORBID, BaseModel, ConfigDict, Field
from dbgpt.configs.model_config import get_device
from dbgpt.core import RerankEmbeddings
from dbgpt.core.interface.parameter import RerankerDeployModelParameters
from dbgpt.model.adapter.base import register_embedding_adapter
from dbgpt.model.adapter.embed_metadata import (
    RERANKER_COMMON_HF_MODELS,
    RERANKER_COMMON_HF_QWEN_MODELS,
)
from dbgpt.util.i18n_utils import _
from dbgpt.util.tracer import DBGPT_TRACER_SPAN_ID, root_tracer


@dataclass
class CrossEncoderRerankEmbeddingsParameters(RerankerDeployModelParameters):
    """CrossEncoder Rerank Embeddings Parameters."""

    provider: str = "hf"
    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _("The path of the model, if you want to deploy a local model."),
        },
    )
    device: Optional[str] = field(
        default=None,
        metadata={
            "order": -700,
            "help": _(
                "Device to run model. If None, the device is automatically determined"
            ),
        },
    )
    max_length: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "Max length for input sequences. Longer sequences will be truncated."
            )
        },
    )

    model_kwargs: Dict[str, Any] = field(
        default_factory=dict,
        metadata={
            "help": _("Keyword arguments to pass to the model."),
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.path or self.name

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path.

        If deploy model is not local, return None.
        """
        return self._resolve_root_path(self.path)

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device."""
        return self.device or super().real_device

    @property
    def real_model_kwargs(self) -> Dict:
        """Get the real model kwargs."""
        model_kwargs = self.model_kwargs or {}
        if self.device:
            model_kwargs["device"] = self.device
        return model_kwargs


class CrossEncoderRerankEmbeddings(BaseModel, RerankEmbeddings):
    """CrossEncoder Rerank Embeddings."""

    model_config = ConfigDict(extra=EXTRA_FORBID, protected_namespaces=())

    client: Any  #: :meta private:
    model_name: str = "BAAI/bge-reranker-base"
    max_length: Optional[int] = None
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

    @classmethod
    def param_class(cls) -> Type[CrossEncoderRerankEmbeddingsParameters]:
        """Get the parameter class."""
        return CrossEncoderRerankEmbeddingsParameters

    @classmethod
    def from_parameters(
        cls, parameters: CrossEncoderRerankEmbeddingsParameters
    ) -> "RerankEmbeddings":
        """Create a rerank model from parameters."""
        return cls(
            model_name=parameters.real_model_path,
            max_length=parameters.max_length,
            model_kwargs=parameters.real_model_kwargs,
        )

    @classmethod
    def _match(
        cls, provider: str, lower_model_name_or_path: Optional[str] = None
    ) -> bool:
        """Check if the model name matches the rerank model."""
        return (
            super()._match(provider, lower_model_name_or_path)
            and lower_model_name_or_path
            and (
                "reranker" in lower_model_name_or_path
                or "rerank" in lower_model_name_or_path
            )
        )

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


@dataclass
class QwenRerankEmbeddingsParameters(RerankerDeployModelParameters):
    """Qwen Rerank Embeddings Parameters."""

    provider: str = "qwen"
    path: Optional[str] = field(
        default=None,
        metadata={
            "order": -800,
            "help": _(
                "The path of the model, if you want to deploy a local model. Defaults "
                "to 'Qwen/Qwen3-Reranker-0.6B'."
            ),
        },
    )
    device: Optional[str] = field(
        default=None,
        metadata={
            "order": -700,
            "help": _(
                "Device to run model. If None, the device is automatically determined"
            ),
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.path or self.name

    @property
    def real_model_path(self) -> Optional[str]:
        """Get the real model path.

        If deploy model is not local, return None.
        """
        return self._resolve_root_path(self.path)

    @property
    def real_device(self) -> Optional[str]:
        """Get the real device."""
        return self.device or super().real_device


class QwenRerankEmbeddings(BaseModel, RerankEmbeddings):
    """Qwen Rerank Embeddings.

    .. code-block:: python
        from dbgpt.rag.embedding.rerank import QwenRerankEmbeddings

        reranker = QwenRerankEmbeddings(model_name="Qwen/Qwen3-Reranker-0.6B")
        query = "Apple"
        documents = [
            "apple",
            "banana",
            "fruit",
            "vegetable",
            "苹果",
            "Mac OS",
            "乔布斯",
            "iPhone",
        ]
        scores = reranker.predict(query, candidates)
        print(scores)
    """

    model_config = ConfigDict(extra=EXTRA_FORBID, protected_namespaces=())
    model_name: str = "Qwen/Qwen3-Reranker-0.6B"
    max_length: int = 8192
    model: Any  #: :meta private:
    tokenizer: Any  #: :meta private:
    token_false_id: int  #: :meta private:
    token_true_id: int  #: :meta private:
    prefix_tokens: List[int]  #: :meta private:
    suffix_tokens: List[int]  #: :meta private:
    task: str = (
        "Given a web search query, retrieve relevant passages that answer the "
        "query"
    )  #: :meta private:
    device: Optional[str] = None  #: :meta private:

    def __init__(self, **kwargs: Any):
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError:
            raise ImportError(
                "please `pip install transformers`",
            )

        try:
            import torch  # noqa: F401
        except ImportError:
            raise ImportError(
                "please `pip install torch`",
            )
        tokenizer = AutoTokenizer.from_pretrained(
            kwargs.get("model_name", "Qwen/Qwen3-Reranker-0.6B"), padding_side="left"
        )
        model = AutoModelForCausalLM.from_pretrained(
            kwargs.get("model_name", "Qwen/Qwen3-Reranker-0.6B"),
        ).eval()
        device = kwargs.get("device", get_device())
        if device:
            model = model.to(device=device)

        token_false_id = tokenizer.convert_tokens_to_ids("no")
        token_true_id = tokenizer.convert_tokens_to_ids("yes")
        prefix = (
            "<|im_start|>system\nJudge whether the Document meets the requirements"
            " based on the Query and the Instruct provided. Note that the answer can "
            'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
        )
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
        suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)

        kwargs["model"] = model
        kwargs["tokenizer"] = tokenizer
        kwargs["token_false_id"] = token_false_id
        kwargs["token_true_id"] = token_true_id
        kwargs["prefix_tokens"] = prefix_tokens
        kwargs["suffix_tokens"] = suffix_tokens
        super().__init__(**kwargs)

    @classmethod
    def param_class(cls) -> Type[QwenRerankEmbeddingsParameters]:
        """Get the parameter class."""
        return QwenRerankEmbeddingsParameters

    @classmethod
    def from_parameters(
        cls, parameters: QwenRerankEmbeddingsParameters
    ) -> "RerankEmbeddings":
        """Create a rerank model from parameters."""
        return cls(
            model_name=parameters.real_model_path,
            device=parameters.real_device,
        )

    def format_instruction(self, instruction, query, doc):
        if instruction is None:
            instruction = (
                "Given a web search query, retrieve relevant passages that "
                "answer the query"
            )
        output = (
            "<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}".format(
                instruction=instruction, query=query, doc=doc
            )
        )
        return output

    def process_inputs(self, pairs):
        inputs = self.tokenizer(
            pairs,
            padding=False,
            truncation="longest_first",
            return_attention_mask=False,
            max_length=self.max_length
            - len(self.prefix_tokens)
            - len(self.suffix_tokens),
        )
        for i, ele in enumerate(inputs["input_ids"]):
            inputs["input_ids"][i] = self.prefix_tokens + ele + self.suffix_tokens
        inputs = self.tokenizer.pad(
            inputs, padding=True, return_tensors="pt", max_length=self.max_length
        )
        for key in inputs:
            inputs[key] = inputs[key].to(self.model.device)
        return inputs

    def compute_logits(self, inputs, **kwargs):
        import torch

        with torch.no_grad():
            batch_scores = self.model(**inputs).logits[:, -1, :]
            true_vector = batch_scores[:, self.token_true_id]
            false_vector = batch_scores[:, self.token_false_id]
            batch_scores = torch.stack([false_vector, true_vector], dim=1)
            batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
            scores = batch_scores[:, 1].exp().tolist()
            return scores

    def predict(self, query: str, candidates: List[str]) -> List[float]:
        queries = [query] * len(candidates)
        pairs = [
            self.format_instruction(self.task, query, doc)
            for query, doc in zip(queries, candidates)
        ]
        # Tokenize the input texts
        inputs = self.process_inputs(pairs)
        scores = self.compute_logits(inputs)
        return scores


@dataclass
class OpenAPIRerankerDeployModelParameters(RerankerDeployModelParameters):
    """OpenAPI Reranker Deploy Model Parameters."""

    provider: str = "proxy/openapi"

    api_url: str = field(
        default="http://localhost:8100/v1/beta/relevance",
        metadata={
            "help": _("The URL of the rerank API."),
        },
    )
    api_key: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The API key for the rerank API."),
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

    timeout: int = field(
        default=60,
        metadata={
            "help": _("The timeout for the request in seconds."),
        },
    )

    @property
    def real_provider_model_name(self) -> str:
        """Get the real provider model name."""
        return self.backend or self.name


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
    pass_trace_id: bool = Field(
        default=True, description="Whether to pass the trace ID to the API."
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

    @classmethod
    def param_class(cls) -> Type[OpenAPIRerankerDeployModelParameters]:
        """Get the parameter class."""
        return OpenAPIRerankerDeployModelParameters

    @classmethod
    def from_parameters(
        cls, parameters: OpenAPIRerankerDeployModelParameters
    ) -> "RerankEmbeddings":
        """Create a rerank model from parameters."""
        return cls(
            api_url=parameters.api_url,
            api_key=parameters.api_key,
            model_name=parameters.real_provider_model_name,
            timeout=parameters.timeout,
        )

    def _parse_results(self, response: Dict[str, Any]) -> List[float]:
        """Parse the response from the API.

        Args:
            response: The response from the API.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        data = response.get("data")
        if not data:
            if "detail" in response:
                raise RuntimeError(response["detail"])
            raise RuntimeError("Cannot find results in the response")
        if not isinstance(data, list):
            raise RuntimeError("Results should be a list")
        return data

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
        headers = {}
        current_span_id = root_tracer.get_current_span_id()
        if self.pass_trace_id and current_span_id:
            # Set the trace ID if available
            headers[DBGPT_TRACER_SPAN_ID] = current_span_id
        data = {"model": self.model_name, "query": query, "documents": candidates}
        response = self.session.post(  # type: ignore
            self.api_url, json=data, timeout=self.timeout, headers=headers
        )
        response.raise_for_status()
        return self._parse_results(response.json())

    async def apredict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the rank scores of the candidates asynchronously."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        current_span_id = root_tracer.get_current_span_id()
        if self.pass_trace_id and current_span_id:
            # Set the trace ID if available
            headers[DBGPT_TRACER_SPAN_ID] = current_span_id
        async with aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            data = {"model": self.model_name, "query": query, "documents": candidates}
            async with session.post(self.api_url, json=data) as resp:
                resp.raise_for_status()
                response_data = await resp.json()
                return self._parse_results(response_data)


@dataclass
class SiliconFlowRerankEmbeddingsParameters(OpenAPIRerankerDeployModelParameters):
    """SiliconFlow Rerank Embeddings Parameters."""

    provider: str = "proxy/siliconflow"

    api_url: str = field(
        default="https://api.siliconflow.cn/v1/rerank",
        metadata={
            "help": _("The URL of the rerank API."),
        },
    )
    api_key: Optional[str] = field(
        default="${env:SILICONFLOW_API_KEY}",
        metadata={
            "help": _("The API key for the rerank API."),
        },
    )


class SiliconFlowRerankEmbeddings(OpenAPIRerankEmbeddings):
    """SiliconFlow Rerank Model.

    See `SiliconFlow API
    <https://docs.siliconflow.cn/api-reference/rerank/create-rerank>`_ for more details.
    """

    def __init__(self, **kwargs: Any):
        """Initialize the SiliconFlowRerankEmbeddings."""
        # If the API key is not provided, try to get it from the environment
        if "api_key" not in kwargs:
            kwargs["api_key"] = os.getenv("SILICONFLOW_API_KEY")

        if "api_url" not in kwargs:
            env_api_url = os.getenv("SILICONFLOW_API_BASE")
            if env_api_url:
                env_api_url = env_api_url.rstrip("/")
                kwargs["api_url"] = env_api_url + "/rerank"
            else:
                kwargs["api_url"] = "https://api.siliconflow.cn/v1/rerank"

        if "model_name" not in kwargs:
            kwargs["model_name"] = "BAAI/bge-reranker-v2-m3"

        super().__init__(**kwargs)

    @classmethod
    def param_class(cls) -> Type[SiliconFlowRerankEmbeddingsParameters]:
        """Get the parameter class."""
        return SiliconFlowRerankEmbeddingsParameters

    def _parse_results(self, response: Dict[str, Any]) -> List[float]:
        """Parse the response from the API.

        Args:
            response: The response from the API.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        results = response.get("results")
        if not results:
            raise RuntimeError("Cannot find results in the response")
        if not isinstance(results, list):
            raise RuntimeError("Results should be a list")
        # Sort by index, 0 in the first element
        results = sorted(results, key=lambda x: x.get("index", 0))
        scores = [float(result.get("relevance_score")) for result in results]
        return scores


@dataclass
class TeiEmbeddingsParameters(OpenAPIRerankerDeployModelParameters):
    """Text Embeddings Inference  Rerank Embeddings Parameters."""

    provider: str = "proxy/tei"

    api_url: str = field(
        default="http://localhost:8001/rerank",
        metadata={
            "help": _("The URL of the rerank API."),
        },
    )
    api_key: Optional[str] = field(
        default=None,
        metadata={
            "help": _("The API key for the rerank API."),
        },
    )


class TeiRerankEmbeddings(OpenAPIRerankEmbeddings):
    """Text Embeddings Inference Rerank Model.

    See `Text Embeddings Inference API
    <https://huggingface.github.io/text-embeddings-inference/>`_ for more details.
    """

    def __init__(self, **kwargs: Any):
        """Initialize the TeiRerankEmbeddings."""
        # If the API key is not provided, try to get it from the environment
        if "api_key" not in kwargs:
            kwargs["api_key"] = os.getenv("TEI_API_KEY")

        if "api_url" not in kwargs:
            raise ValueError("Please provide the api_url param")

        super().__init__(**kwargs)

    @classmethod
    def param_class(cls) -> Type[TeiEmbeddingsParameters]:
        """Get the parameter class."""
        return TeiEmbeddingsParameters

    def _parse_results(self, response: List[Dict[str, Any]]) -> List[float]:
        """Parse the response from the API.

        Args:
            response: The response from the API.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        if not isinstance(response, list) and len(response) == 0:
            raise RuntimeError("Results should be a not empty list")

        # Sort by index, 0 in the first element
        results = sorted(response, key=lambda x: x.get("index", 0))
        scores = [float(result.get("score")) for result in results]
        return scores

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
        headers = {}
        current_span_id = root_tracer.get_current_span_id()
        if self.pass_trace_id and current_span_id:
            # Set the trace ID if available
            headers[DBGPT_TRACER_SPAN_ID] = current_span_id
        data = {"query": query, "texts": candidates}
        response = self.session.post(  # type: ignore
            self.api_url, json=data, timeout=self.timeout, headers=headers
        )
        response.raise_for_status()
        return self._parse_results(response.json())

    async def apredict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the rank scores of the candidates asynchronously."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        current_span_id = root_tracer.get_current_span_id()
        if self.pass_trace_id and current_span_id:
            # Set the trace ID if available
            headers[DBGPT_TRACER_SPAN_ID] = current_span_id
        async with aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as session:
            data = {"query": query, "texts": candidates}
            async with session.post(self.api_url, json=data) as resp:
                resp.raise_for_status()
                response_data = await resp.json()
                return self._parse_results(response_data)


@dataclass
class InfiniAIRerankEmbeddingsParameters(OpenAPIRerankerDeployModelParameters):
    """InfiniAI Rerank Embeddings Parameters."""

    provider: str = "proxy/infiniai"

    api_url: str = field(
        default="https://cloud.infini-ai.com/maas/v1/rerank",
        metadata={
            "help": _("The URL of the rerank API."),
        },
    )
    api_key: Optional[str] = field(
        default="${env:INFINIAI_API_KEY}",
        metadata={
            "help": _("The API key for the rerank API."),
        },
    )


class InfiniAIRerankEmbeddings(OpenAPIRerankEmbeddings):
    """InfiniAI Rerank Model.

    See `InfiniAI API
    <https://docs.infini-ai.com/gen-studio/api/tutorial-rerank.html>`_ for more details.
    """

    def __init__(self, **kwargs: Any):
        """Initialize the InfiniAIRerankEmbeddings."""
        # If the API key is not provided, try to get it from the environment
        if "api_key" not in kwargs:
            kwargs["api_key"] = os.getenv("InfiniAI_API_KEY")

        if "api_url" not in kwargs:
            env_api_url = os.getenv("InfiniAI_API_BASE")
            if env_api_url:
                env_api_url = env_api_url.rstrip("/")
                kwargs["api_url"] = env_api_url + "/rerank"
            else:
                kwargs["api_url"] = "https://cloud.infini-ai.com/maas/v1/rerank"

        if "model_name" not in kwargs:
            kwargs["model_name"] = "bge-reranker-v2-m3"

        super().__init__(**kwargs)

    @classmethod
    def param_class(cls) -> Type[InfiniAIRerankEmbeddingsParameters]:
        """Get the parameter class."""
        return InfiniAIRerankEmbeddingsParameters

    def _parse_results(self, response: Dict[str, Any]) -> List[float]:
        """Parse the response from the API.

        Args:
            response: The response from the API.

        Returns:
            List[float]: The rank scores of the candidates.
        """
        results = response.get("results")
        if not results:
            raise RuntimeError("Cannot find results in the response")
        if not isinstance(results, list):
            raise RuntimeError("Results should be a list")
        # Sort by index, 0 in the first element
        results = sorted(results, key=lambda x: x.get("index", 0))
        scores = [float(result.get("relevance_score")) for result in results]
        return scores


register_embedding_adapter(
    CrossEncoderRerankEmbeddings, supported_models=RERANKER_COMMON_HF_MODELS
)
register_embedding_adapter(
    OpenAPIRerankEmbeddings, supported_models=RERANKER_COMMON_HF_MODELS
)
register_embedding_adapter(
    SiliconFlowRerankEmbeddings, supported_models=RERANKER_COMMON_HF_MODELS
)
register_embedding_adapter(
    TeiRerankEmbeddings, supported_models=RERANKER_COMMON_HF_MODELS
)
register_embedding_adapter(
    InfiniAIRerankEmbeddings, supported_models=RERANKER_COMMON_HF_MODELS
)
register_embedding_adapter(
    QwenRerankEmbeddings, supported_models=RERANKER_COMMON_HF_QWEN_MODELS
)
