from dbgpt.util.memory_utils import _get_object_bytes

from ..base import MemoryCacheStorage, StorageItem


def test_build_from():
    key_hash = b"key_hash"
    key_data = b"key_data"
    value_data = b"value_data"
    item = StorageItem.build_from(key_hash, key_data, value_data)

    assert item.key_hash == key_hash
    assert item.key_data == key_data
    assert item.value_data == value_data
    assert item.length == 32 + _get_object_bytes(key_hash) + _get_object_bytes(
        key_data
    ) + _get_object_bytes(value_data)


def test_build_from_kv():
    class MockCacheKey:
        def get_hash_bytes(self):
            return b"key_hash"

        def serialize(self):
            return b"key_data"

    class MockCacheValue:
        def serialize(self):
            return b"value_data"

    key = MockCacheKey()
    value = MockCacheValue()
    item = StorageItem.build_from_kv(key, value)

    assert item.key_hash == key.get_hash_bytes()
    assert item.key_data == key.serialize()
    assert item.value_data == value.serialize()


def test_serialize_deserialize():
    key_hash = b"key_hash"
    key_data = b"key_data"
    value_data = b"value_data"
    item = StorageItem.build_from(key_hash, key_data, value_data)

    serialized = item.serialize()
    deserialized = StorageItem.deserialize(serialized)

    assert deserialized.key_hash == item.key_hash
    assert deserialized.key_data == item.key_data
    assert deserialized.value_data == item.value_data
    assert deserialized.length == item.length


class SizedCacheKey:
    def __init__(self, name: str):
        self.name = name

    def __hash__(self):
        return hash(self.name)

    def get_hash_bytes(self):
        return self.name.encode()

    def serialize(self):
        return self.name.encode()


class SizedCacheValue:
    def __init__(self, size: int):
        self.size = size

    def serialize(self):
        return b"x" * self.size


def test_memory_cache_evicts_only_what_it_needs():
    storage = MemoryCacheStorage(max_memory_mb=1)
    for i in range(10):
        storage.set(SizedCacheKey(f"k{i}"), SizedCacheValue(200 * 1024))

    assert len(storage.cache) > 1
    assert storage.exists(SizedCacheKey("k9"))


def test_memory_cache_usage_drops_on_evict():
    storage = MemoryCacheStorage(max_memory_mb=1)
    for i in range(10):
        storage.set(SizedCacheKey(f"k{i}"), SizedCacheValue(200 * 1024))

    assert storage.current_memory_usage <= storage.max_memory
    assert storage.current_memory_usage >= len(storage.cache) * 200 * 1024


def test_memory_cache_accepts_entry_larger_than_max():
    storage = MemoryCacheStorage(max_memory_mb=1)
    storage.set(SizedCacheKey("small"), SizedCacheValue(1024))
    storage.set(SizedCacheKey("big"), SizedCacheValue(2 * 1024 * 1024))

    assert storage.exists(SizedCacheKey("big"))
