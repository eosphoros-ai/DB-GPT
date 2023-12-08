import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp
from dbgpt.util.tracer import TracerContext, Tracer


_DEFAULT_EXCLUDE_PATHS = ["/api/controller/heartbeat"]


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

        span_id = request.headers.get("DBGPT_TRACER_SPAN_ID")
        # if not span_id:
        #     span_id = str(uuid.uuid4())
        # self.trace_context_var.set(TracerContext(span_id=span_id))

        with self.tracer.start_span(
            self.root_operation_name, span_id, metadata={"path": request.url.path}
        ):
            response = await call_next(request)
        return response
