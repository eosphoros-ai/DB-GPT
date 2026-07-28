"""Tests for DomainKnowledgeIndexFactory."""

import pytest

from ..base import DomainKnowledgeIndex
from ..factory import DomainKnowledgeIndexFactory
from ..index import DomainGeneralIndex


class TestDomainKnowledgeIndexFactory:
    def test_create_normal_index(self):
        index = DomainKnowledgeIndexFactory.create("normal")
        assert isinstance(index, DomainGeneralIndex)
        assert index.domain_type() == "normal"

    def test_create_normal_index_case_insensitive(self):
        index = DomainKnowledgeIndexFactory.create("Normal")
        assert isinstance(index, DomainGeneralIndex)

    def test_create_unknown_index_raises(self):
        with pytest.raises(Exception, match="not supported"):
            DomainKnowledgeIndexFactory.create("unknown_type")

    def test_available_types_includes_normal(self):
        types = DomainKnowledgeIndexFactory.available_types()
        assert "normal" in types

    def test_domain_general_index_is_subclass(self):
        assert issubclass(DomainGeneralIndex, DomainKnowledgeIndex)
