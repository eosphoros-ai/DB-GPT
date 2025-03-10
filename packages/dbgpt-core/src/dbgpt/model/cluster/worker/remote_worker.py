import json
import logging
from typing import Dict, Iterator, List

from dbgpt.core import ModelMetadata, ModelOutput
from dbgpt.model.cluster.worker_base import ModelWorker
from dbgpt.util.tracer import DBGPT_TRACER_SPAN_ID, root_tracer

logger = logging.getLogger(__name__)


class RemoteModelWorker(ModelWorker):
    def __init__(self) -> None:
        self.headers = {}
        # TODO Configured by ModelParameters
        self.timeout = 3600
        self.host = None
        self.port = None

    @property
    def worker_addr(self) -> str:
        return f"http://{self.host}:{self.port}/api/worker"

    def support_async(self) -> bool:
        return True

    # def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
    #     return None

    def load_worker(self, model_name: str, **kwargs):
        self.host = kwargs.get("host")
        self.port = kwargs.get("port")

    def start(self, command_args: List[str] = None) -> None:
        """Start model worker"""
        pass

    def stop(self) -> None:
        raise NotImplementedError("Remote model worker not support stop methods")

    def generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        """Generate stream"""
        raise NotImplementedError

    async def async_generate_stream(self, params: Dict) -> Iterator[ModelOutput]:
        """Asynchronous generate stream"""
        import httpx

        async with httpx.AsyncClient() as client:
            delimiter = b"\0"
            buffer = b""
            url = self.worker_addr + "/generate_stream"
            logger.debug(f"Send async_generate_stream to url {url}, params: {params}")
            async with client.stream(
                "POST",
                url,
                headers=self._get_trace_headers(),
                json=params,
                timeout=self.timeout,
            ) as response:
                async for raw_chunk in response.aiter_raw():
                    buffer += raw_chunk
                    while delimiter in buffer:
                        chunk, buffer = buffer.split(delimiter, 1)
                        if not chunk:
                            continue
                        chunk = chunk.decode()
                        data = json.loads(chunk)
                        yield ModelOutput(**data)

    def generate(self, params: Dict) -> ModelOutput:
        """Generate non stream"""
        raise NotImplementedError

    async def async_generate(self, params: Dict) -> ModelOutput:
        """Asynchronous generate non stream"""
        import httpx

        async with httpx.AsyncClient() as client:
            url = self.worker_addr + "/generate"
            logger.debug(f"Send async_generate to url {url}, params: {params}")
            response = await client.post(
                url,
                headers=self._get_trace_headers(),
                json=params,
                timeout=self.timeout,
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Request to {url} failed, error: {response.text}")
            return ModelOutput(**response.json())

    def count_token(self, prompt: str) -> int:
        raise NotImplementedError

    async def async_count_token(self, prompt: str) -> int:
        import httpx

        async with httpx.AsyncClient() as client:
            url = self.worker_addr + "/count_token"
            logger.debug(f"Send async_count_token to url {url}, params: {prompt}")
            response = await client.post(
                url,
                headers=self._get_trace_headers(),
                json={"prompt": prompt},
                timeout=self.timeout,
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Request to {url} failed, error: {response.text}")
            return response.json()

    async def async_get_model_metadata(self, params: Dict) -> ModelMetadata:
        """Asynchronously get model metadata"""
        import httpx

        async with httpx.AsyncClient() as client:
            url = self.worker_addr + "/model_metadata"
            logger.debug(
                f"Send async_get_model_metadata to url {url}, params: {params}"
            )
            response = await client.post(
                url,
                headers=self._get_trace_headers(),
                json=params,
                timeout=self.timeout,
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Request to {url} failed, error: {response.text}")
            return ModelMetadata.from_dict(response.json())

    def get_model_metadata(self, params: Dict) -> ModelMetadata:
        """Get model metadata"""
        raise NotImplementedError

    def embeddings(self, params: Dict) -> List[List[float]]:
        """Get embeddings for input"""
        import requests

        url = self.worker_addr + "/embeddings"
        logger.debug(f"Send embeddings to url {url}, params: {params}")
        response = requests.post(
            url,
            headers=self._get_trace_headers(),
            json=params,
            timeout=self.timeout,
        )
        if response.status_code not in [200, 201]:
            raise Exception(f"Request to {url} failed, error: {response.text}")
        return response.json()

    async def async_embeddings(self, params: Dict) -> List[List[float]]:
        """Asynchronous get embeddings for input"""
        import httpx

        async with httpx.AsyncClient() as client:
            url = self.worker_addr + "/embeddings"
            logger.debug(f"Send async_embeddings to url {url}")
            response = await client.post(
                url,
                headers=self._get_trace_headers(),
                json=params,
                timeout=self.timeout,
            )
            if response.status_code not in [200, 201]:
                raise Exception(f"Request to {url} failed, error: {response.text}")
            return response.json()

    def _get_trace_headers(self):
        span_id = root_tracer.get_current_span_id()
        headers = self.headers.copy()
        if span_id:
            headers.update({DBGPT_TRACER_SPAN_ID: span_id})
        return headers
