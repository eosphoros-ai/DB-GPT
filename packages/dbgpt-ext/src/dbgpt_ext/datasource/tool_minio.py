"""MinIO read-only tool for DB-GPT.

Provides safe, read-only MinIO object storage operations exposed as DB-GPT tools.
Connection details are read from environment variables:
  - MINIO_ENDPOINT (default: localhost:9000)
  - MINIO_ACCESS_KEY (default: minioadmin)
  - MINIO_SECRET_KEY (default: minioadmin)
  - MINIO_SECURE (default: false, set to "true" for HTTPS)
"""

import json
import os
from typing import Optional

from dbgpt.agent.resource.tool.base import tool

from minio import Minio

_minio_client: Optional[Minio] = None


def _get_client() -> Minio:
    global _minio_client
    if _minio_client is not None:
        return _minio_client
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
    _minio_client = Minio(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=secure,
    )
    return _minio_client


@tool
def minio_list_buckets() -> str:
    """List all MinIO buckets."""
    client = _get_client()
    buckets = client.list_buckets()
    result = [{"name": b.name, "created": b.creation_date.isoformat() if b.creation_date else None} for b in buckets]
    return json.dumps({"buckets": result}, ensure_ascii=False)


@tool
def minio_list_objects(bucket: str, prefix: str = "", max_keys: int = 50) -> str:
    """List objects in a MinIO bucket with optional prefix filter.

    Args:
        bucket: The bucket name.
        prefix: Optional prefix to filter objects.
        max_keys: Maximum number of objects to return (default 50).
    """
    client = _get_client()
    objects = client.list_objects(bucket, prefix=prefix or "")
    result = []
    count = 0
    for obj in objects:
        if count >= max_keys:
            break
        result.append({
            "name": obj.object_name,
            "size": obj.size,
            "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
        })
        count += 1
    return json.dumps({"bucket": bucket, "prefix": prefix, "objects": result, "count": len(result)}, ensure_ascii=False)


@tool
def minio_get_object(bucket: str, object_name: str) -> str:
    """Download and return the content of a MinIO object as text (max 1MB).

    Args:
        bucket: The bucket name.
        object_name: The object key/name.
    """
    client = _get_client()
    try:
        response = client.get_object(bucket, object_name)
        content = response.read(1024 * 1024)  # max 1 MB
        response.close()
        response.release_conn()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = f"<binary data, {len(content)} bytes>"
        return json.dumps(
            {"bucket": bucket, "object_name": object_name, "size": len(content), "content": text},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e), "bucket": bucket, "object_name": object_name}, ensure_ascii=False)


@tool
def minio_stat_object(bucket: str, object_name: str) -> str:
    """Get metadata for a MinIO object without downloading content.

    Args:
        bucket: The bucket name.
        object_name: The object key/name.
    """
    client = _get_client()
    try:
        stat = client.stat_object(bucket, object_name)
        return json.dumps(
            {
                "bucket": stat.bucket_name,
                "object_name": stat.object_name,
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e), "bucket": bucket, "object_name": object_name}, ensure_ascii=False)
