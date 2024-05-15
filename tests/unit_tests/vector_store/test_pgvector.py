from dbgpt.rag.index.base import IndexStoreConfig
from dbgpt.storage import vector_store


def test_vetorestore_imports() -> None:
    """Simple test to make sure all things can be imported."""

    for cls in vector_store.__all__:
        store_cls, config_cls = getattr(vector_store, cls)
        from dbgpt.rag.index.base import IndexStoreBase

        assert issubclass(store_cls, IndexStoreBase)
        assert issubclass(config_cls, IndexStoreConfig)
