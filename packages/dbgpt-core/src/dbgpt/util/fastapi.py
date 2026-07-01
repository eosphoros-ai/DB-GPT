"""FastAPI utilities."""

import importlib.metadata as metadata
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI
from fastapi.routing import APIRouter

_FASTAPI_VERSION = metadata.version("fastapi")


class PriorityAPIRouter(APIRouter):
    """A router with priority.

    The route with higher priority will be put in the front of the route list.
    """

    def __init__(self, *args, **kwargs):
        """Init a PriorityAPIRouter."""
        super().__init__(*args, **kwargs)
        self.route_priority: Dict[str, int] = {}

    def add_api_route(
        self, path: str, endpoint: Callable, *, priority: int = 0, **kwargs: Any
    ):
        """Add a route with priority.

        Args:
            path (str): The path of the route.
            endpoint (Callable): The endpoint of the route.
            priority (int, optional): The priority of the route. Defaults to 0.
            **kwargs (Any): Other arguments.
        """
        super().add_api_route(path, endpoint, **kwargs)
        self.route_priority[path] = priority
        # Sort the routes by priority.
        self.sort_routes_by_priority()

    def sort_routes_by_priority(self):
        """Sort the routes by priority."""

        def my_func(route):
            if route.path in ["", "/"]:
                return -100
            return self.route_priority.get(route.path, 0)

        self.routes.sort(key=my_func, reverse=True)


_HAS_STARTUP = False
_HAS_SHUTDOWN = False
_GLOBAL_STARTUP_HANDLERS: List[Callable] = []

_GLOBAL_SHUTDOWN_HANDLERS: List[Callable] = []


def register_event_handler(app: FastAPI, event: str, handler: Callable):
    """Register an event handler.

    Args:
        app (FastAPI): The FastAPI app.
        event (str): The event type.
        handler (Callable): The handler function.

    """
    if _FASTAPI_VERSION >= "0.109.1":
        # https://fastapi.tiangolo.com/release-notes/#01091
        if event == "startup":
            if _HAS_STARTUP:
                raise ValueError(
                    "FastAPI app already started. Cannot add startup handler."
                )
            _GLOBAL_STARTUP_HANDLERS.append(handler)
        elif event == "shutdown":
            if _HAS_SHUTDOWN:
                raise ValueError(
                    "FastAPI app already shutdown. Cannot add shutdown handler."
                )
            _GLOBAL_SHUTDOWN_HANDLERS.append(handler)
        else:
            raise ValueError(f"Invalid event: {event}")
    else:
        if event == "startup":
            app.add_event_handler("startup", handler)
        elif event == "shutdown":
            app.add_event_handler("shutdown", handler)
        else:
            raise ValueError(f"Invalid event: {event}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Trigger the startup event.
    global _HAS_STARTUP, _HAS_SHUTDOWN
    for handler in _GLOBAL_STARTUP_HANDLERS:
        await handler()
    _HAS_STARTUP = True
    yield
    # Trigger the shutdown event.
    for handler in _GLOBAL_SHUTDOWN_HANDLERS:
        await handler()
    _HAS_SHUTDOWN = True


def create_app(*args, **kwargs) -> FastAPI:
    """Create a FastAPI app."""
    _sp = None
    if _FASTAPI_VERSION >= "0.109.1":
        if "lifespan" not in kwargs:
            kwargs["lifespan"] = lifespan
        _sp = kwargs["lifespan"]
    app = FastAPI(*args, **kwargs)
    if _sp:
        app.__dbgpt_custom_lifespan = _sp
    return app


def replace_router(app: FastAPI, router: Optional[APIRouter] = None):
    """Replace the router of the FastAPI app."""
    if not router:
        router = PriorityAPIRouter()
    if _FASTAPI_VERSION >= "0.109.1":
        if hasattr(app, "__dbgpt_custom_lifespan"):
            _sp = getattr(app, "__dbgpt_custom_lifespan")
            router.lifespan_context = _sp

    app.router = router
    app.setup()
    return app


def build_cors_config(allow_origins: Optional[str]) -> Dict[str, Any]:
    """Build CORS middleware kwargs from a comma-separated origins string.

    Shared by the webserver (``dbgpt-app``) and the model apiserver
    (``dbgpt-core``) so both honor the same ``cors_allowed_origins`` setting
    without coupling to each other's parameter classes.

    Args:
        allow_origins (Optional[str]): Comma-separated allowed origins. ``"*"``
            (or empty/None) allows all origins. Otherwise a literal origin list,
            e.g. ``"http://localhost:3000,https://your-app.com"``.

    Returns:
        Dict[str, Any]: Keyword arguments for ``CORSMiddleware`` (without
        ``app``; the caller supplies ``app``).

    Notes:
        - ``"*"`` is returned with ``allow_credentials=False`` because W3C
          CORS forbids ``Access-Control-Allow-Origin: *`` together with
          ``Access-Control-Allow-Credentials: true``. The previous hardcoded
          ``["*"]`` + ``allow_credentials=True`` was an invalid combination.
        - An explicit origin list is returned with ``allow_credentials=True``
          so cookie/credential-bearing cross-origin requests keep working.
    """
    raw = (allow_origins or "*").strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    allow_all = not origins or "*" in origins
    return {
        "allow_origins": ["*"] if allow_all else origins,
        "allow_credentials": not allow_all,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
    }
