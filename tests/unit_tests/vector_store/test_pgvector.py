import pytest

from pilot import vector_store
from pilot.vector_store.base import VectorStoreBase


def test_vetorestore_imports() -> None:
    """Simple test to make sure all things can be imported."""

    for cls in vector_store.__all__:
        assert issubclass(getattr(vector_store, cls), VectorStoreBase)
