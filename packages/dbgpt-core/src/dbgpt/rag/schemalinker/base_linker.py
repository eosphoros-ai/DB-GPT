"""Base Linker."""

from abc import ABC, abstractmethod
from typing import List


class BaseSchemaLinker(ABC):
    """Base Linker."""

    def schema_linking(self, query: str) -> List:
        """Query schema info.

        Args:
            query (str): query text
        Returns:
            List: list of schema
        """
        return self._schema_linking(query)

    def schema_linking_with_vector_db(self, query: str) -> List:
        """Query schema info with vector db.

        Args:
            query (str): query text
        Returns:
            List: list of schema
        """
        return self._schema_linking_with_vector_db(query)

    async def schema_linking_with_llm(self, query: str) -> List:
        """Query schema info with llm.

        Args:
            query(str): query text
        Returns:
        List: list of schema
        """
        return await self._schema_linking_with_llm(query)

    @abstractmethod
    def _schema_linking(self, query: str) -> List:
        """Get DB schema info.

        Args:
            query (str): query text
        Returns:
            List: list of schema
        """

    @abstractmethod
    def _schema_linking_with_vector_db(self, query: str) -> List:
        """Query schema info with vector db.

        Args:
            query (str): query text
        Returns:
            List: list of schema
        """

    @abstractmethod
    async def _schema_linking_with_llm(self, query: str) -> List:
        """Query schema info with llm.

        Args:
            query (str): query text
        Returns:
            List: list of schema
        """
