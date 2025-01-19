import asyncio
import logging
import threading
import time
from abc import ABC
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from inspect import signature
from typing import List, Literal, Optional, Tuple, Type, TypeVar, Union, get_type_hints

T = TypeVar("T")

logger = logging.getLogger(__name__)


class APIMixin(ABC):
    """API mixin class."""

    def __init__(
        self,
        urls: Union[str, List[str]],
        health_check_path: str,
        health_check_interval_secs: int = 5,
        health_check_timeout_secs: int = 30,
        check_health: bool = True,
        choice_type: Literal["latest_first", "random"] = "latest_first",
        executor: Optional[Executor] = None,
    ):
        if isinstance(urls, str):
            # Split by ","
            urls = urls.split(",")
        urls = [url.strip() for url in urls]
        self._remote_urls = urls
        self._health_check_path = health_check_path
        self._health_urls = []
        self._health_check_interval_secs = health_check_interval_secs
        self._health_check_timeout_secs = health_check_timeout_secs
        self._heartbeat_map = {}
        self._choice_type = choice_type
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_checker)
        self._heartbeat_executor = executor or ThreadPoolExecutor(max_workers=3)
        self._heartbeat_stop_event = threading.Event()

        if check_health:
            self._heartbeat_thread.daemon = True
            self._heartbeat_thread.start()

    def _heartbeat_checker(self):
        logger.debug("Running health check")
        while not self._heartbeat_stop_event.is_set():
            try:
                healthy_urls = self._check_and_update_health()
                logger.debug(f"Healthy urls: {healthy_urls}")
            except Exception as e:
                logger.warning(f"Health check failed, error: {e}")
            time.sleep(self._health_check_interval_secs)

    def __del__(self):
        self._heartbeat_stop_event.set()

    def _check_health(self, url: str) -> Tuple[bool, str]:
        try:
            import requests

            logger.debug(f"Checking health for {url}")
            req_url = url + self._health_check_path
            response = requests.get(req_url, timeout=10)
            return response.status_code == 200, url
        except Exception as e:
            logger.warning(f"Health check failed for {url}, error: {e}")
            return False, url

    def _check_and_update_health(self) -> List[str]:
        """Check health of all remote urls and update the health urls list."""
        check_tasks = []
        check_results = []
        for url in self._remote_urls:
            check_tasks.append(self._heartbeat_executor.submit(self._check_health, url))
        for task in check_tasks:
            check_results.append(task.result())
        now = datetime.now()
        for is_healthy, url in check_results:
            if is_healthy:
                self._heartbeat_map[url] = now
        healthy_urls = []
        for url, last_heartbeat in self._heartbeat_map.items():
            if now - last_heartbeat < timedelta(
                seconds=self._health_check_interval_secs
            ):
                healthy_urls.append((url, last_heartbeat))
        # Sort by last heartbeat time, latest first
        healthy_urls.sort(key=lambda x: x[1], reverse=True)

        self._health_urls = [url for url, _ in healthy_urls]
        return self._health_urls

    async def select_url(self, max_wait_health_timeout_secs: int = 2) -> str:
        """Select a healthy url to send request.

        If no healthy urls found, select randomly.
        """
        import random

        def _select(urls: List[str]):
            if self._choice_type == "latest_first":
                return urls[0]
            elif self._choice_type == "random":
                return random.choice(urls)
            else:
                raise ValueError(f"Invalid choice type: {self._choice_type}")

        if self._health_urls:
            return _select(self._health_urls)
        elif max_wait_health_timeout_secs > 0:
            start_time = datetime.now()
            while datetime.now() - start_time < timedelta(
                seconds=max_wait_health_timeout_secs
            ):
                if self._health_urls:
                    return _select(self._health_urls)
                await asyncio.sleep(0.1)
        logger.warning("No healthy urls found, selecting randomly")
        return _select(self._remote_urls)

    def sync_select_url(self, max_wait_health_timeout_secs: int = 2) -> str:
        """Synchronous version of select_url."""
        import random
        import time

        def _select(urls: List[str]):
            if self._choice_type == "latest_first":
                return urls[0]
            elif self._choice_type == "random":
                return random.choice(urls)
            else:
                raise ValueError(f"Invalid choice type: {self._choice_type}")

        if self._health_urls:
            return _select(self._health_urls)
        elif max_wait_health_timeout_secs > 0:
            start_time = datetime.now()
            while datetime.now() - start_time < timedelta(
                seconds=max_wait_health_timeout_secs
            ):
                if self._health_urls:
                    return _select(self._health_urls)
                time.sleep(0.1)
        logger.warning("No healthy urls found, selecting randomly")
        return _select(self._remote_urls)


def _extract_dataclass_from_generic(type_hint: Type[T]) -> Union[Type[T], None]:
    """Extract actual dataclass from generic type hints like List[dataclass],
    Optional[dataclass], etc.
    """

    import typing_inspect

    if typing_inspect.is_generic_type(type_hint) and typing_inspect.get_args(type_hint):
        return typing_inspect.get_args(type_hint)[0]
    return None


def _build_request(self, base_url, func, path, method, *args, **kwargs):
    return_type = get_type_hints(func).get("return")
    if return_type is None:
        raise TypeError("Return type must be annotated in the decorated function.")

    actual_dataclass = _extract_dataclass_from_generic(return_type)
    logger.debug(f"return_type: {return_type}, actual_dataclass: {actual_dataclass}")
    if not actual_dataclass:
        actual_dataclass = return_type
    sig = signature(func)

    bound = sig.bind(self, *args, **kwargs)
    bound.apply_defaults()

    formatted_url = base_url + path.format(**bound.arguments)

    # Extract args names from signature, except "self"
    arg_names = list(sig.parameters.keys())[1:]

    # Combine args and kwargs into a single dictionary
    combined_args = dict(zip(arg_names, args))
    combined_args.update(kwargs)

    request_data = {}
    for key, value in combined_args.items():
        if is_dataclass(value):
            # Here, instead of adding it as a nested dictionary,
            # we set request_data directly to its dictionary representation.
            request_data = asdict(value)
        else:
            request_data[key] = value

    request_params = {"method": method, "url": formatted_url}

    if method in ["POST", "PUT", "PATCH"]:
        request_params["json"] = request_data
    else:  # For GET, DELETE, etc.
        request_params["params"] = request_data

    logger.debug(f"request_params: {request_params}, args: {args}, kwargs: {kwargs}")
    return return_type, actual_dataclass, request_params


def _api_remote(path: str, method: str = "GET", max_wait_health_timeout_secs: int = 2):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            import httpx

            if not isinstance(self, APIMixin):
                raise TypeError(
                    "The class must inherit from APIMixin to use the @_api_remote "
                    "decorator."
                )
            # Found a healthy url to send request
            base_url = await self.select_url(
                max_wait_health_timeout_secs=max_wait_health_timeout_secs
            )
            return_type, actual_dataclass, request_params = _build_request(
                self, base_url, func, path, method, *args, **kwargs
            )
            async with httpx.AsyncClient() as client:
                response = await client.request(**request_params)
                if response.status_code == 200:
                    return _parse_response(
                        response.json(), return_type, actual_dataclass
                    )
                else:
                    error_msg = (
                        "Remote request error, error code: "
                        f"{response.status_code}, error msg: {response.text}"
                    )
                    raise Exception(error_msg)

        return wrapper

    return decorator


def _sync_api_remote(
    path: str, method: str = "GET", max_wait_health_timeout_secs: int = 2
):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            import requests

            if not isinstance(self, APIMixin):
                raise TypeError(
                    "The class must inherit from APIMixin to use the @_sync_api_remote "
                    "decorator."
                )
            base_url = self.sync_select_url(
                max_wait_health_timeout_secs=max_wait_health_timeout_secs
            )

            return_type, actual_dataclass, request_params = _build_request(
                self, base_url, func, path, method, *args, **kwargs
            )

            response = requests.request(**request_params)

            if response.status_code == 200:
                return _parse_response(response.json(), return_type, actual_dataclass)
            else:
                error_msg = (
                    f"Remote request error, error code: {response.status_code},"
                    f" error msg: {response.text}"
                )
                raise Exception(error_msg)

        return wrapper

    return decorator


def _parse_response(json_response, return_type, actual_dataclass):
    if is_dataclass(actual_dataclass):
        if return_type.__origin__ is list:  # for List[dataclass]
            if isinstance(json_response, list):
                return [actual_dataclass(**item) for item in json_response]
            else:
                raise TypeError(
                    f"Expected list in response but got {type(json_response)}"
                )
        else:
            if isinstance(json_response, dict):
                return actual_dataclass(**json_response)
            else:
                raise TypeError(
                    f"Expected dictionary in response but got {type(json_response)}"
                )
    else:
        return json_response
