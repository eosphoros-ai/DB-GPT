import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import (
    Any,
    Dict,
    Optional,
    Protocol,
    Set,
    Union,
)

import cloudpickle

logger = logging.getLogger(__name__)


class CacheStorage(Protocol):
    """Protocol for cache storage implementations."""

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value for a key."""
        ...

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache value for a key with optional TTL in seconds."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...


class MemoryCacheStorage:
    """Simple in-memory implementation of CacheStorage."""

    def __init__(self):
        """Initialize an empty cache."""
        self._cache: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value for a key."""
        return self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cache value for a key.

        Note: This implementation ignores TTL.
        """
        self._cache[key] = value

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache


class FileCacheStorage:
    """File-based cache storage implementation using cloudpickle for serialization.

    This implementation stores each cache entry as a separate file in the specified
    cache directory. Metadata including expiration time is stored in a separate
    file for each cache entry.

    Supports tracking new cache entries and rolling back if needed.
    """

    def __init__(
        self,
        cache_dir: Union[str, Path] = ".cache",
        create_dir: bool = True,
        hash_keys: bool = True,
    ):
        """Initialize a file-based cache storage.

        Args:
            cache_dir: Directory to store cache files
            create_dir: Whether to create the cache directory if it doesn't exist
            hash_keys: Whether to hash cache keys to avoid filesystem issues with
            special characters
        """
        self._cache_dir = Path(cache_dir)
        self._hash_keys = hash_keys

        if create_dir and not self._cache_dir.exists():
            os.makedirs(self._cache_dir, exist_ok=True)

        if not self._cache_dir.is_dir():
            raise ValueError(f"Cache directory {self._cache_dir} is not a directory")

        # Track new cache entries for potential rollback
        self._new_cache_entries: Set[str] = set()

    def _get_key_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        if self._hash_keys:
            # Hash the key to avoid filesystem issues with special characters
            hashed_key = hashlib.md5(key.encode("utf-8")).hexdigest()
            return self._cache_dir / f"{hashed_key}.cache"
        return self._cache_dir / f"{key}.cache"

    def _get_meta_path(self, key: str) -> Path:
        """Get the metadata file path for a cache key."""
        key_path = self._get_key_path(key)
        return key_path.with_suffix(".meta")

    async def _save_metadata(self, key: str, ttl: Optional[int] = None) -> None:
        """Save metadata for a cache entry."""
        meta_path = self._get_meta_path(key)

        metadata = {
            "key": key,
            "created_at": time.time(),
            "expires_at": time.time() + ttl if ttl is not None else None,
        }

        # Use a separate threadpool for file I/O to avoid blocking
        await asyncio.to_thread(self._write_metadata, meta_path, metadata)

    def _write_metadata(self, path: Path, metadata: Dict[str, Any]) -> None:
        """Write metadata to file (runs in a separate thread)."""
        with open(path, "wb") as f:
            cloudpickle.dump(metadata, f)

    async def _load_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Load metadata for a cache entry."""
        meta_path = self._get_meta_path(key)

        if not meta_path.exists():
            return None

        try:
            # Run file I/O in a separate thread
            return await asyncio.to_thread(self._read_metadata, meta_path)
        except Exception as e:
            logger.warning(f"Failed to load metadata for {key}: {e}")
            return None

    def _read_metadata(self, path: Path) -> Dict[str, Any]:
        """Read metadata from file (runs in a separate thread)."""
        with open(path, "rb") as f:
            return cloudpickle.load(f)

    async def _is_expired(self, key: str) -> bool:
        """Check if a cache entry is expired."""
        metadata = await self._load_metadata(key)

        if metadata is None:
            return True

        expires_at = metadata.get("expires_at")

        if expires_at is None:
            return False

        return time.time() > expires_at

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache and is not expired."""
        key_path = self._get_key_path(key)
        meta_path = self._get_meta_path(key)

        if not key_path.exists() or not meta_path.exists():
            return False

        # Check if the entry is expired
        is_expired = await self._is_expired(key)

        if is_expired:
            # Clean up expired entries
            await asyncio.gather(
                asyncio.to_thread(self._remove_file, key_path),
                asyncio.to_thread(self._remove_file, meta_path),
            )
            return False

        return True

    def _remove_file(self, path: Path) -> None:
        """Remove a file if it exists (runs in a separate thread)."""
        if path.exists():
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"Failed to remove {path}: {e}")

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Returns None if the key doesn't exist or is expired.
        """
        if not await self.exists(key):
            return None

        key_path = self._get_key_path(key)

        try:
            # Run file I/O in a separate thread
            return await asyncio.to_thread(self._read_value, key_path)
        except Exception as e:
            logger.warning(f"Failed to read cache value for {key}: {e}")
            return None

    def _read_value(self, path: Path) -> Any:
        """Read a value from a file (runs in a separate thread)."""
        with open(path, "rb") as f:
            return cloudpickle.load(f)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache with an optional TTL in seconds.

        This method also tracks the key as a new cache entry for potential rollback.
        """
        key_path = self._get_key_path(key)

        # Track this as a new cache entry (only if it doesn't already exist)
        if not await self.exists(key):
            self._new_cache_entries.add(key)

        # Use a separate threadpool for file I/O operations
        await asyncio.gather(
            asyncio.to_thread(self._write_value, key_path, value),
            self._save_metadata(key, ttl),
        )

    def _write_value(self, path: Path, value: Any) -> None:
        """Write a value to a file (runs in a separate thread)."""
        # Ensure the directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temporary file first to avoid corruption if the process is
        # interrupted
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                cloudpickle.dump(value, f)

            # Atomic replace (as much as the OS allows)
            if os.name == "posix":
                # On POSIX systems, rename is atomic
                os.rename(temp_path, path)
            else:
                # On Windows, we try to be as safe as possible
                if path.exists():
                    os.remove(path)
                os.rename(temp_path, path)
        finally:
            # Clean up temp file if it still exists
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except Exception as _e:
                    pass

    async def clear(self) -> None:
        """Clear all cache entries."""
        try:
            cache_files = list(self._cache_dir.glob("*.cache")) + list(
                self._cache_dir.glob("*.meta")
            )

            # Remove all files in parallel
            await asyncio.gather(
                *[asyncio.to_thread(self._remove_file, file) for file in cache_files]
            )

            # Clear tracking
            self._new_cache_entries.clear()
        except Exception as e:
            logger.warning(f"Failed to clear cache: {e}")

    async def remove(self, key: str) -> bool:
        """Remove a specific key from the cache.

        Returns True if the key was removed, False otherwise.
        """
        key_path = self._get_key_path(key)
        meta_path = self._get_meta_path(key)

        if not key_path.exists() and not meta_path.exists():
            return False

        try:
            # Remove both the value and metadata files
            await asyncio.gather(
                asyncio.to_thread(self._remove_file, key_path),
                asyncio.to_thread(self._remove_file, meta_path),
            )

            # Remove from tracking if present
            if key in self._new_cache_entries:
                self._new_cache_entries.remove(key)

            return True
        except Exception as e:
            logger.warning(f"Failed to remove {key} from cache: {e}")
            return False

    async def commit(self) -> None:
        """Commit all pending cache changes.

        This simply clears the tracking of new cache entries.
        """
        self._new_cache_entries.clear()

    async def rollback(self) -> None:
        """Roll back all new cache entries since the last commit.

        This removes all cache entries that were added since tracking began.
        """
        # Make a copy of the set to avoid modification during iteration
        entries_to_remove = self._new_cache_entries.copy()

        # Remove each new entry
        for key in entries_to_remove:
            await self.remove(key)

        # Clear tracking
        self._new_cache_entries.clear()


# Additional utility function to handle streaming from cached data
async def stream_from_cached_data(cached_data):
    """Convert cached data back into an async generator for streaming responses.

    This is needed because cloudpickle cannot directly serialize async generators,
    so we store the actual values and recreate the generator when needed.

    Args:
        cached_data: The cached data, typically a list of items that were
                    collected from a stream, or a single item.

    Yields:
        Items from the cached data, one at a time, mimicking the original stream.
    """
    if isinstance(cached_data, list):
        for item in cached_data:
            yield item
    else:
        # If it's not a list (single item), just yield it once
        yield cached_data
