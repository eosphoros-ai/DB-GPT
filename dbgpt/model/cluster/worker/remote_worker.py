import json
from typing import Dict, Iterator, List
import logging
from dbgpt.core import ModelOutput
from dbgpt.model.parameter import ModelParameters
from dbgpt.model.cluster.worker_base import ModelWorker


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

    def parse_parameters(self, command_args: List[str] = None) -> ModelParameters:
        return None

    def load_worker(self, model_name: str, model_path: str, **kwargs):
        self.host = kwargs.get("host")
        self.port = kwargs.get("port")

    def start(
        self, model_params: ModelParameters = None, command_args: List[str] = None
    ) -> None:
        """Start model worker"""
        pass
        # raise NotImplementedError("Remote model worker not support start methods")

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
                headers=self.headers,
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
                headers=self.headers,
                json=params,
                timeout=self.timeout,
            )
            return ModelOutput(**response.json())

    def embeddings(self, params: Dict) -> List[List[float]]:
        """Get embeddings for input"""
        import requests

        url = self.worker_addr + "/embeddings"
        logger.debug(f"Send embeddings to url {url}, params: {params}")
        response = requests.post(
            url,
            headers=self.headers,
            json=params,
            timeout=self.timeout,
        )
        return response.json()

    async def async_embeddings(self, params: Dict) -> List[List[float]]:
        """Asynchronous get embeddings for input"""
        import httpx

        async with httpx.AsyncClient() as client:
            url = self.worker_addr + "/embeddings"
            logger.debug(f"Send async_embeddings to url {url}")
            response = await client.post(
                url,
                headers=self.headers,
                json=params,
                timeout=self.timeout,
            )
            return response.json()
