from inspect import signature
import logging
from typing import get_type_hints, List, Type, TypeVar, Union, Optional, Tuple
from dataclasses import is_dataclass, asdict

T = TypeVar("T")

logger = logging.getLogger(__name__)


def _extract_dataclass_from_generic(type_hint: Type[T]) -> Union[Type[T], None]:
    import typing_inspect

    """Extract actual dataclass from generic type hints like List[dataclass], Optional[dataclass], etc."""
    if typing_inspect.is_generic_type(type_hint) and typing_inspect.get_args(type_hint):
        return typing_inspect.get_args(type_hint)[0]
    return None


def _build_request(self, func, path, method, *args, **kwargs):
    return_type = get_type_hints(func).get("return")
    if return_type is None:
        raise TypeError("Return type must be annotated in the decorated function.")

    actual_dataclass = _extract_dataclass_from_generic(return_type)
    logger.debug(f"return_type: {return_type}, actual_dataclass: {actual_dataclass}")
    if not actual_dataclass:
        actual_dataclass = return_type
    sig = signature(func)
    base_url = self.base_url  # Get base_url from class instance

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


def _api_remote(path, method="GET"):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            import httpx

            return_type, actual_dataclass, request_params = _build_request(
                self, func, path, method, *args, **kwargs
            )
            async with httpx.AsyncClient() as client:
                response = await client.request(**request_params)
                if response.status_code == 200:
                    return _parse_response(
                        response.json(), return_type, actual_dataclass
                    )
                else:
                    error_msg = f"Remote request error, error code: {response.status_code}, error msg: {response.text}"
                    raise Exception(error_msg)

        return wrapper

    return decorator


def _sync_api_remote(path, method="GET"):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            import requests

            return_type, actual_dataclass, request_params = _build_request(
                self, func, path, method, *args, **kwargs
            )

            response = requests.request(**request_params)

            if response.status_code == 200:
                return _parse_response(response.json(), return_type, actual_dataclass)
            else:
                error_msg = f"Remote request error, error code: {response.status_code}, error msg: {response.text}"
                raise Exception(error_msg)

        return wrapper

    return decorator


def _parse_response(json_response, return_type, actual_dataclass):
    # print(f'return_type.__origin__: {return_type.__origin__}, actual_dataclass: {actual_dataclass}, json_response: {json_response}')
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
