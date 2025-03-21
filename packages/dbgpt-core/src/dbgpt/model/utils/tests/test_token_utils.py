import sys
import time
from collections import OrderedDict

from dbgpt.model.utils.token_utils import LRUTokenCache


class TestLRUTokenCache:
    """Comprehensive tests for the LRUTokenCache class"""

    def test_init(self):
        """Test initialization of the cache"""
        # Test default parameters
        cache = LRUTokenCache()
        assert cache.max_size == 1000
        assert cache.max_memory_bytes == 100 * 1024 * 1024
        assert isinstance(cache.cache, OrderedDict)
        assert cache.current_memory == 0

        # Test custom parameters
        cache = LRUTokenCache(max_size=500, max_memory_mb=50)
        assert cache.max_size == 500
        assert cache.max_memory_bytes == 50 * 1024 * 1024

        # Test with zero max_size (should set to at least 1)
        cache = LRUTokenCache(max_size=0)
        assert cache.max_size == 1

    def test_put_and_get_basic(self):
        """Test basic put and get functionality"""
        cache = LRUTokenCache(max_size=10, max_memory_mb=10)

        # Add an item and retrieve it
        cache.put("key1", 100)
        assert cache.get("key1") == 100

        # Check non-existent key
        assert cache.get("nonexistent") is None

        # Add multiple items
        cache.put("key2", 200)
        cache.put("key3", 300)

        assert cache.get("key1") == 100
        assert cache.get("key2") == 200
        assert cache.get("key3") == 300

    def test_lru_ordering(self):
        """Test LRU ordering when getting items"""
        cache = LRUTokenCache(max_size=3, max_memory_mb=10)

        # Add items
        cache.put("key1", 100)
        cache.put("key2", 200)
        cache.put("key3", 300)

        # Access key1, making it most recently used
        cache.get("key1")

        # Internal order should now be: key2, key3, key1
        order = list(cache.cache.keys())
        assert order[0] == "key2"
        assert order[1] == "key3"
        assert order[2] == "key1"

        # Access key2, making it most recently used
        cache.get("key2")

        # Internal order should now be: key3, key1, key2
        order = list(cache.cache.keys())
        assert order[0] == "key3"
        assert order[1] == "key1"
        assert order[2] == "key2"

    def test_eviction_by_count(self):
        """Test eviction of oldest items when cache size limit is reached"""
        cache = LRUTokenCache(max_size=3, max_memory_mb=10)

        # Add 3 items to fill the cache
        cache.put("key1", 100)
        cache.put("key2", 200)
        cache.put("key3", 300)

        # Add a 4th item, which should evict the oldest (key1)
        cache.put("key4", 400)

        # key1 should be evicted
        assert cache.get("key1") is None
        assert cache.get("key2") == 200
        assert cache.get("key3") == 300
        assert cache.get("key4") == 400

        # Access key2, making it most recently used
        cache.get("key2")

        # Add a 5th item, which should evict the oldest (now key3)
        cache.put("key5", 500)

        # key3 should now be evicted
        assert cache.get("key3") is None
        assert cache.get("key2") == 200
        assert cache.get("key4") == 400
        assert cache.get("key5") == 500

    def test_update_existing_key(self):
        """Test updating an existing key"""
        cache = LRUTokenCache(max_size=3, max_memory_mb=10)

        # Add 3 items
        cache.put("key1", 100)
        cache.put("key2", 200)
        cache.put("key3", 300)

        # Update key1 with a new value
        cache.put("key1", 150)

        # Check the updated value
        assert cache.get("key1") == 150

        # key1 should now be the most recently used
        order = list(cache.cache.keys())
        assert order[2] == "key1"

        # Cache size should still be 3
        assert len(cache.cache) == 3

    def test_eviction_by_memory(self):
        """Test eviction based on memory limits"""
        # Create a cache with very small memory limit - just enough for one large item
        large_key = "large_key"
        large_value = 999

        # Calculate memory needed for the large item
        single_item_size = sys.getsizeof(large_key) + sys.getsizeof(large_value)
        # Set memory limit to exactly fit this item plus a small buffer
        mem_limit_mb = (single_item_size + 50) / (1024 * 1024)

        cache = LRUTokenCache(max_size=10, max_memory_mb=mem_limit_mb)

        # Add first item
        cache.put("key1", 100)

        # Add the large item that should cause eviction
        cache.put(large_key, large_value)

        # key1 should be evicted because the large item won't fit otherwise
        assert cache.get("key1") is None
        assert cache.get(large_key) == large_value

        # Only the large item should be in the cache
        assert len(cache.cache) == 1

    def test_multiple_eviction_for_large_item(self):
        """Test that multiple items are evicted if necessary for a large item"""
        # Create a cache with specific memory limit
        cache = LRUTokenCache(max_size=10, max_memory_mb=0.01)  # 10KB

        # First, we'll see how many small items we can fit in our limit
        for i in range(20):  # Try with more than enough items
            key = f"key{i}"
            cache.put(key, i * 100)
            if len(cache.cache) < i + 1:
                # The cache didn't grow, we've hit the memory limit
                break

        # Remember how many items we could fit
        initial_items = len(cache.cache)
        assert initial_items > 0, "Could not fit any items in cache"

        # Create a larger value that should force eviction
        large_key = "x" * 500  # Bigger key
        large_value = 9999  # Bigger value

        # Calculate approximate size
        large_item_size = sys.getsizeof(large_key) + sys.getsizeof(large_value)

        # Get existing keys before adding large item
        existing_keys = list(cache.cache.keys())

        # Add the large item
        cache.put(large_key, large_value)

        # Check if the large item was added
        assert cache.get(large_key) == large_value

        # Check that the memory usage did not exceed the limit
        assert cache.current_memory <= cache.max_memory_bytes

        # Either:
        # 1. The large item caused evictions and total should be less than before + 1
        # 2. The large item fit without evictions and total should be before + 1
        if large_item_size > (cache.max_memory_bytes / 2):
            # If large item takes significant space, expect evictions
            assert len(cache.cache) <= initial_items

            # Check that at least one original item was evicted
            evicted = False
            for key in existing_keys:
                if cache.get(key) is None:
                    evicted = True
                    break
            assert evicted, "No items were evicted for large item"

    def test_clear(self):
        """Test clearing the cache"""
        cache = LRUTokenCache(max_size=10, max_memory_mb=10)

        # Add some items
        cache.put("key1", 100)
        cache.put("key2", 200)
        cache.put("key3", 300)

        # Clear the cache
        cache.clear()

        # Cache should be empty
        assert len(cache.cache) == 0
        assert cache.current_memory == 0

        # All items should be gone
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_last_access_time_update(self):
        """Test that last access time is updated properly"""
        cache = LRUTokenCache(max_size=10, max_memory_mb=10)

        # Add an item
        cache.put("key1", 100)

        # Get the initial last access time
        initial_time = cache.cache["key1"][2]

        # Wait a moment to ensure time difference
        time.sleep(0.01)

        # Access the item
        cache.get("key1")

        # Check that the last access time was updated
        updated_time = cache.cache["key1"][2]
        assert updated_time > initial_time

    def test_edge_cases(self):
        """Test edge cases"""
        # Cache of size 1
        cache = LRUTokenCache(max_size=1, max_memory_mb=10)
        cache.put("key1", 100)
        cache.put("key2", 200)
        assert cache.get("key1") is None
        assert cache.get("key2") == 200

        # Cache with 0 size should still maintain at least 1 item
        cache = LRUTokenCache(max_size=0, max_memory_mb=10)
        cache.put("key1", 100)
        assert cache.get("key1") == 100

        # Very small memory limit
        tiny_limit = 1 / (1024 * 1024)  # 1 byte (in MB)
        cache = LRUTokenCache(max_size=10, max_memory_mb=tiny_limit)
        # This should work without error (it might not keep the item, but shouldn't
        # crash)
        cache.put("key1", 100)

        # Updating existing key in a full cache
        cache = LRUTokenCache(max_size=1, max_memory_mb=10)
        cache.put("key1", 100)
        cache.put("key1", 200)  # Update, shouldn't cause eviction of itself
        assert cache.get("key1") == 200
