"""Redis read-only tool for DB-GPT.

Provides safe, read-only Redis operations exposed as DB-GPT tools.
Connection details are read from environment variables:
  - REDIS_HOST (default: localhost)
  - REDIS_PORT (default: 6379)
  - REDIS_PASSWORD (default: empty)
  - REDIS_DB (default: 0)
"""

import json
import os
from typing import Any, Optional

from redis import Redis

from dbgpt.agent.resource.tool.base import tool

_redis_client: Optional[Redis] = None


def _get_client() -> Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    _redis_client = Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    return _redis_client


@tool
def redis_get(key: str) -> str:
    """Read a string value from Redis by key.

    Args:
        key: The Redis key to read.
    """
    client = _get_client()
    value = client.get(key)
    return json.dumps({"key": key, "value": value}, ensure_ascii=False)


@tool
def redis_hget(key: str, field: str) -> str:
    """Read a hash field value from Redis.

    Args:
        key: The Redis hash key.
        field: The hash field name.
    """
    client = _get_client()
    value = client.hget(key, field)
    return json.dumps({"key": key, "field": field, "value": value}, ensure_ascii=False)


@tool
def redis_hgetall(key: str) -> str:
    """Read all fields and values of a Redis hash.

    Args:
        key: The Redis hash key.
    """
    client = _get_client()
    value = client.hgetall(key)
    return json.dumps({"key": key, "hash": value}, ensure_ascii=False)


@tool
def redis_keys(pattern: str) -> str:
    """List Redis keys matching a glob pattern (read-only, use with caution).

    Args:
        pattern: Glob pattern, e.g. 'user:*' or 'session:*'.
    """
    client = _get_client()
    keys = client.keys(pattern)
    return json.dumps({"pattern": pattern, "keys": keys[:100]}, ensure_ascii=False)


@tool
def redis_type(key: str) -> str:
    """Get the data type of a Redis key.

    Args:
        key: The Redis key to inspect.
    """
    client = _get_client()
    t = client.type(key)
    return json.dumps({"key": key, "type": t}, ensure_ascii=False)


@tool
def redis_ttl(key: str) -> str:
    """Get the remaining TTL (seconds) of a Redis key. Returns -1 if no TTL, -2 if key does not exist.

    Args:
        key: The Redis key.
    """
    client = _get_client()
    ttl = client.ttl(key)
    return json.dumps({"key": key, "ttl_seconds": ttl}, ensure_ascii=False)
