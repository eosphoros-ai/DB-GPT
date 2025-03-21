from __future__ import annotations

import logging
import sys
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from dbgpt.core.interface.message import BaseMessage, ModelMessage

logger = logging.getLogger(__name__)


class ProxyTokenizerWrapper:
    def __init__(self) -> None:
        self._support_encoding = True
        self._encoding_model = None

    def count_token(
        self,
        messages: Union[str, BaseMessage, ModelMessage, List[ModelMessage]],
        model_name: Optional[str] = None,
    ) -> int:
        """Count token of given messages

        Args:
            messages (Union[str, BaseMessage, ModelMessage, List[ModelMessage]]):
                messages to count token
            model_name (Optional[str], optional): model name. Defaults to None.

        Returns:
            int: token count, -1 if failed
        """
        if not self._support_encoding:
            logger.warning(
                "model does not support encoding model, can't count token, returning -1"
            )
            return -1
        encoding = self._get_or_create_encoding_model(model_name)
        cnt = 0
        if isinstance(messages, str):
            cnt = len(encoding.encode(messages, disallowed_special=()))
        elif isinstance(messages, BaseMessage):
            cnt = len(encoding.encode(messages.content, disallowed_special=()))
        elif isinstance(messages, ModelMessage):
            cnt = len(encoding.encode(messages.content, disallowed_special=()))
        elif isinstance(messages, list):
            for message in messages:
                cnt += len(encoding.encode(message.content, disallowed_special=()))
        else:
            logger.warning(
                "unsupported type of messages, can't count token, returning -1"
            )
            return -1
        return cnt

    def _get_or_create_encoding_model(self, model_name: Optional[str] = None):
        """Get or create encoding model for given model name
        More detail see: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        """
        if self._encoding_model:
            return self._encoding_model
        try:
            import tiktoken

            logger.info(
                "tiktoken installed, using it to count tokens, tiktoken will download "
                "tokenizer from network, also you can download it and put it in the "
                "directory of environment variable TIKTOKEN_CACHE_DIR"
            )
        except ImportError:
            self._support_encoding = False
            logger.warn("tiktoken not installed, cannot count tokens, returning -1")
            return -1
        try:
            if not model_name:
                model_name = "gpt-3.5-turbo"
            self._encoding_model = tiktoken.model.encoding_for_model(model_name)
        except KeyError:
            logger.warning(
                f"{model_name}'s tokenizer not found, using cl100k_base encoding."
            )
            self._encoding_model = tiktoken.get_encoding("cl100k_base")
        return self._encoding_model


class LRUTokenCache:
    """LRU cache implementation based on count and memory size for token counting
    results"""

    def __init__(self, max_size: int = 1000, max_memory_mb: float = 100):
        """
        Initialize LRU cache

        Args:
            max_size: Maximum number of cache entries
            max_memory_mb: Maximum memory usage (MB)
        """
        # Ensure max_size is at least 1
        self.max_size = max(1, max_size)
        self.max_memory_bytes = max_memory_mb * 1024 * 1024  # Convert to bytes
        self.cache = OrderedDict()  # {key: (value, size_in_bytes, last_access_time)}
        self.current_memory = 0  # Current total memory usage (bytes)

    def get(self, key):
        """Get cache item and update its position"""
        if key not in self.cache:
            return None

        # Get cached value and update access time
        value, size, _ = self.cache[key]
        current_time = time.time()

        # Update cache item position (move to most recently used position)
        self.cache.move_to_end(key)
        # Update last access time
        self.cache[key] = (value, size, current_time)

        return value

    def put(self, key, value):
        """
        Add or update a cache item

        Args:
            key: Cache key
            value: Cache value (token count)
        """
        # Estimate memory size for an integer token count
        size_estimate = sys.getsizeof(key) + sys.getsizeof(value)
        current_time = time.time()

        # If key already exists, remove old value's memory usage
        if key in self.cache:
            _, old_size, _ = self.cache[key]
            self.current_memory -= old_size
            # Move to most recently used position
            self.cache.move_to_end(key)

        # If adding new item would exceed memory limit, delete old items until there's
        # enough space
        while (
            self.current_memory + size_estimate > self.max_memory_bytes
            and self.cache
            and len(self.cache) > 0
        ):
            # Make sure the item we're evicting isn't the one we're about to update
            if len(self.cache) == 1 and key in self.cache:
                # If we only have one item and it's the key we're updating,
                # we should just update it instead of trying to evict
                break

            oldest_key, (_, oldest_size, _) = next(iter(self.cache.items()))
            if oldest_key == key:
                # Skip evicting the key we're about to update
                # Move to the next oldest item
                self.cache.move_to_end(oldest_key)
                if len(self.cache) <= 1:
                    break
                oldest_key, (_, oldest_size, _) = next(iter(self.cache.items()))

            self.cache.pop(oldest_key)  # Remove oldest item
            self.current_memory -= oldest_size
            logger.debug(
                f"LRU cache: Removed token count entry '{oldest_key}' due to memory "
                "limit"
            )

        # If reached count limit but not memory limit, remove oldest item
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Check if the cache is not empty before trying to pop
            if self.cache:
                oldest_key, (_, oldest_size, _) = next(iter(self.cache.items()))
                self.cache.pop(oldest_key)
                self.current_memory -= oldest_size
                logger.debug(
                    f"LRU cache: Removed token count entry '{oldest_key}' due to count "
                    "limit"
                )

        # Add new item
        self.cache[key] = (value, size_estimate, current_time)
        self.current_memory += size_estimate

    def clear(self):
        """Clear the cache"""
        self.cache.clear()
        self.current_memory = 0

    def __len__(self):
        """Return the number of items in the cache"""
        return len(self.cache)
