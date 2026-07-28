"""Factory for creating DomainKnowledgeIndex instances."""

import logging
from typing import List, Type

from .base import DomainKnowledgeIndex

logger = logging.getLogger(__name__)


class DomainKnowledgeIndexFactory:
    @staticmethod
    def create(domain_type: str) -> DomainKnowledgeIndex:
        index_cls = DomainKnowledgeIndexFactory._find_type(domain_type)
        try:
            return index_cls()
        except Exception as e:
            logger.error(f"Create domain knowledge index failed: {e}")
            raise e

    @staticmethod
    def _find_type(domain_type: str) -> Type[DomainKnowledgeIndex]:
        for t in DomainKnowledgeIndexFactory._get_index_subclasses():
            if t.domain_type().lower() == domain_type.lower():
                return t
        raise Exception(
            f"Domain knowledge index type '{domain_type}' not supported. "
            f"Available types: {DomainKnowledgeIndexFactory.available_types()}"
        )

    @staticmethod
    def _get_index_subclasses() -> List[Type[DomainKnowledgeIndex]]:
        from .index import DomainGeneralIndex  # noqa: F401

        try:
            from .git_repo_index import GitRepoIndex  # noqa: F401
        except ImportError:
            logger.debug("GitRepoIndex not available")

        def get_all_subclasses(cls):
            result = []
            for sub in cls.__subclasses__():
                result.append(sub)
                result.extend(get_all_subclasses(sub))
            return result

        return get_all_subclasses(DomainKnowledgeIndex)

    @staticmethod
    def available_types() -> List[str]:
        return [
            t.domain_type() for t in DomainKnowledgeIndexFactory._get_index_subclasses()
        ]
