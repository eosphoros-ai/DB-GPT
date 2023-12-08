from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Type

from dbgpt.component import BaseComponent, ComponentType


class RAGGraphFactory(BaseComponent, ABC):
    name = ComponentType.RAG_GRAPH_DEFAULT.value

    @abstractmethod
    def create(self, model_name: str = None, embedding_cls: Type = None):
        """Create RAG Graph Engine"""


class DefaultRAGGraphFactory(RAGGraphFactory):
    def __init__(
        self, system_app=None, default_model_name: str = None, **kwargs: Any
    ) -> None:
        super().__init__(system_app=system_app)
        self._default_model_name = default_model_name
        self.kwargs = kwargs
        from dbgpt.rag.graph_engine.graph_engine import RAGGraphEngine

        self.rag_engine = RAGGraphEngine(model_name="proxyllm")

    def init_app(self, system_app):
        pass

    def create(self, model_name: str = None, rag_cls: Type = None):
        if not model_name:
            model_name = self._default_model_name

        return self.rag_engine
