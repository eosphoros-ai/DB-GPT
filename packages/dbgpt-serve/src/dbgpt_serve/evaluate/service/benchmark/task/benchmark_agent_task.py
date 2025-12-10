"""Benchmark Agent Task module for evaluating remote agent APIs."""

import json
import logging
import time
from dataclasses import asdict
from typing import Any, Dict, Optional, Union

import aiohttp

from dbgpt_serve.evaluate.service.benchmark.models import (
    AgentApiConfig,
    AgentCompletionRequest,
    HttpMethod,
    ReasoningResponse,
    ResponseParseStrategy,
)
from dbgpt_serve.evaluate.service.fetchdata.benchmark_data_manager import (
    get_benchmark_manager,
)

logger = logging.getLogger(__name__)


class ResponseParser:
    """Response parser for extracting content from API responses."""

    @staticmethod
    def parse_json_path(response_data: Any, json_path: str) -> Any:
        """Parse response using JSON path expression.

        Args:
            response_data: The response data (dict or list)
            json_path: JSON path expression (e.g., "$.data.content")

        Returns:
            Extracted value or None if path not found
        """
        if not json_path:
            return response_data

        # Remove leading $. if present
        path = json_path.lstrip("$.")

        # Split path by dots and brackets
        parts = path.replace("[", ".").replace("]", "").split(".")

        current = response_data
        for part in parts:
            if not part:
                continue

            try:
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list):
                    index = int(part)
                    current = current[index]
                else:
                    return None

                if current is None:
                    return None
            except (KeyError, IndexError, ValueError, TypeError):
                return None

        return current

    @staticmethod
    def parse_direct(response_data: Any) -> str:
        """Parse response directly as string.

        Args:
            response_data: The response data

        Returns:
            String representation of the response
        """
        if isinstance(response_data, str):
            return response_data
        elif isinstance(response_data, dict):
            # Try common response fields
            for field in ["content", "result", "answer", "output", "text", "sql"]:
                if field in response_data:
                    return str(response_data[field])
            return json.dumps(response_data, ensure_ascii=False)
        else:
            return str(response_data)


class BenchmarkAgentTask:
    """Benchmark Agent Task for evaluating remote agent APIs.

    This class provides functionality to:
    1. Call remote agent APIs with configurable parameters
    2. Parse API responses according to configuration
    3. Handle retries and error scenarios
    4. Support various HTTP methods and authentication schemes
    """

    def __init__(
        self,
        api_config: AgentApiConfig,
        agent_name: Optional[str] = None,
    ):
        """Initialize the BenchmarkAgentTask.

        Args:
            api_config: Agent API configuration
            agent_name: Optional name for the agent (for logging)
        """
        self._api_config = api_config
        self._agent_name = agent_name or "RemoteAgent"
        self._parser = ResponseParser()

        # Validate configuration
        self._validate_config()

        db_connector = get_benchmark_manager().get_connector()
        if db_connector:
            self.dialect = db_connector.dialect

    def _validate_config(self):
        """Validate the API configuration."""
        if not self._api_config.api_url:
            raise ValueError("API URL is required")

    async def invoke_agent(
        self, prompt: Optional[str] = None, **kwargs
    ) -> Union[ReasoningResponse, None]:
        """Invoke the remote agent API.

        Args:
            prompt: The prompt to send to the agent
            **kwargs: Additional parameters for request body mapping
        Returns:
            ReasoningResponse object or None if request failed
        """
        return await self._invoke_task(prompt, **kwargs)

    async def _invoke_task(
        self, prompt: Optional[str], **kwargs
    ) -> Union[ReasoningResponse, None]:
        """Internal method to invoke the agent task.

        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters

        Returns:
            ReasoningResponse or None
        """
        start_time = time.time()

        # Build request body
        request_body_obj = self._build_request_body(prompt, **kwargs)
        request_body = {
            k: v for k, v in asdict(request_body_obj).items() if v is not None
        }

        # Execute request with retries
        for attempt in range(self._api_config.max_retries):
            try:
                response_data = await self._execute_request(request_body)

                # Parse response
                reasoning_response = self._parse_response(response_data)

                if reasoning_response:
                    logger.info(
                        f"[{self._agent_name}] Successfully invoked agent API, "
                        f"reasoning_response={reasoning_response},"
                        f" duration={(time.time() - start_time):.2f}s"
                    )
                    return reasoning_response
                else:
                    logger.warning(
                        f"[{self._agent_name}] Failed to parse response, "
                        f"attempt={attempt + 1}"
                    )

            except Exception as e:
                logger.error(
                    f"[{self._agent_name}] Request failed on attempt {attempt + 1}: {e}"
                )

                if attempt < self._api_config.max_retries - 1:
                    # Wait before retry
                    await self._async_sleep(self._api_config.retry_delay)
                else:
                    logger.error(f"[{self._agent_name}] All retry attempts exhausted")
                    return None

        return None

    def _build_request_body(
        self, prompt: Optional[str], **kwargs
    ) -> AgentCompletionRequest:
        """Build request body from template and parameters.

        Args:
            prompt: The prompt text
            **kwargs: Additional parameters including model, temperature, top_p,
                     top_k, max_tokens, stream, user, question

        Returns:
            AgentCompletionRequest object
        """
        messages = []
        if prompt:
            messages.append({"role": "user", "content": prompt})

        return AgentCompletionRequest(
            messages=messages,
            temperature=kwargs.get("temperature"),
            top_p=kwargs.get("top_p"),
            top_k=kwargs.get("top_k"),
            max_tokens=kwargs.get("max_tokens"),
            stream=kwargs.get("stream"),
            user=kwargs.get("user"),
        )

    async def _execute_request(self, request_body: Dict[str, Any]) -> Any:
        """Execute HTTP request to the agent API.

        Args:
            request_body: The request body

        Returns:
            Response data (parsed JSON or text)

        Raises:
            Exception: If request fails
        """
        connector = None
        if not self._api_config.verify_ssl:
            connector = aiohttp.TCPConnector(ssl=False)

        timeout = aiohttp.ClientTimeout(total=self._api_config.timeout)

        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            request_kwargs = {
                "url": self._api_config.api_url,
                "headers": self._api_config.headers,
                "params": self._api_config.query_params,
            }

            # Add body for methods that support it
            if self._api_config.http_method in [
                HttpMethod.POST,
                HttpMethod.PUT,
                HttpMethod.PATCH,
            ]:
                request_kwargs["json"] = request_body

            logger.debug(
                f"[{self._agent_name}] Sending {self._api_config.http_method.value} "
                f"request to {self._api_config.api_url}"
            )

            async with session.request(
                self._api_config.http_method.value, **request_kwargs
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")

                # Try to parse as JSON, fallback to text
                try:
                    return await response.json()
                except Exception:
                    return await response.text()

    def _parse_response(self, response_data: Any) -> Optional[ReasoningResponse]:
        """Parse the API response into ReasoningResponse.

        Args:
            response_data: The raw response data

        Returns:
            ReasoningResponse object or None if parsing failed
        """
        try:
            if self._api_config.parse_strategy == ResponseParseStrategy.DIRECT:
                content = self._parser.parse_direct(response_data)
                return ReasoningResponse(content=content, cot_tokens=0, think=None)

            elif self._api_config.parse_strategy == ResponseParseStrategy.JSON_PATH:
                # Extract fields using JSON path
                content = None
                tokens = 0
                think = None

                if "sql" in self._api_config.response_mapping:
                    content = self._parser.parse_json_path(
                        response_data, self._api_config.response_mapping["sql"]
                    )

                if "tokens" in self._api_config.response_mapping:
                    tokens_value = self._parser.parse_json_path(
                        response_data, self._api_config.response_mapping["tokens"]
                    )
                    if tokens_value is not None:
                        try:
                            tokens = int(tokens_value)
                        except (ValueError, TypeError):
                            tokens = 0

                if "think" in self._api_config.response_mapping:
                    think = self._parser.parse_json_path(
                        response_data, self._api_config.response_mapping["think"]
                    )

                # If content is None, try to extract from response directly
                if content is None:
                    content = self._parser.parse_direct(response_data)

                return ReasoningResponse(
                    content=str(content) if content is not None else "",
                    cot_tokens=tokens,
                    think=str(think) if think is not None else None,
                )
        except Exception as e:
            logger.error(
                f"[{self._agent_name}] Failed to parse response: {e}", exc_info=True
            )
        return None

    @staticmethod
    async def _async_sleep(seconds: int):
        """Async sleep utility."""
        import asyncio

        await asyncio.sleep(seconds)

    def get_config(self) -> AgentApiConfig:
        """Get the current API configuration.

        Returns:
            AgentApiConfig object
        """
        return self._api_config

    def update_config(self, **kwargs):
        """Update API configuration.

        Args:
            **kwargs: Configuration fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self._api_config, key):
                setattr(self._api_config, key, value)
            else:
                logger.warning(f"[{self._agent_name}] Unknown config field: {key}")
