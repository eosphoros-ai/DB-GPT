"""Pydantic schemas for the observability serve.

P0 endpoints use query parameters and return the provider's dataclass DTOs
(serialized via :func:`dataclasses.asdict`), so no request/response Pydantic
models are required yet. Add typed schemas here as the API grows.
"""
