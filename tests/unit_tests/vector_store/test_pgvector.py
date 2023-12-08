from dbgpt.storage import vector_store
from dbgpt.storage.vector_store.base import VectorStoreBase


def test_vetorestore_imports() -> None:
    """Simple test to make sure all things can be imported."""

    for cls in vector_store.__all__:
        assert issubclass(getattr(vector_store, cls), VectorStoreBase)
