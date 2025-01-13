from dbgpt.util.memory_utils import _get_object_bytes

from ..base import StorageItem


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
