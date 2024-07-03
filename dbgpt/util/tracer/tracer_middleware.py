import logging
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from dbgpt.util.tracer import Tracer, TracerContext

from .base import _parse_span_id

_DEFAULT_EXCLUDE_PATHS = ["/api/controller/heartbeat", "/api/health"]

logger = logging.getLogger(__name__)


class TraceIDMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        trace_context_var: ContextVar[TracerContext],
        tracer: Tracer,
        root_operation_name: str = "DB-GPT-Web-Entry",
        include_prefix: str = "/api",
        exclude_paths=_DEFAULT_EXCLUDE_PATHS,
    ):
        super().__init__(app)
        self.trace_context_var = trace_context_var
        self.tracer = tracer
        self.root_operation_name = root_operation_name
        self.include_prefix = include_prefix
        self.exclude_paths = exclude_paths

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exclude_paths or not request.url.path.startswith(
            self.include_prefix
        ):
            return await call_next(request)

        # Read trace_id from request headers
        span_id = _parse_span_id(request)
        logger.debug(
            f"TraceIDMiddleware: span_id={span_id}, path={request.url.path}, "
            f"headers={request.headers}"
        )
        with self.tracer.start_span(
            self.root_operation_name, span_id, metadata={"path": request.url.path}
        ):
            response = await call_next(request)
        return response
