"""Knowledge Factory to create knowledge from file path and url."""
from typing import List, Optional, Type

from dbgpt.rag.knowledge.base import Knowledge, KnowledgeType
from dbgpt.rag.knowledge.string import StringKnowledge
from dbgpt.rag.knowledge.url import URLKnowledge


class KnowledgeFactory:
    """Knowledge Factory to create knowledge from file path and url."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
    ):
        """Create Knowledge Factory with file path and knowledge type.

        Args:
            file_path(str, optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
        """
        self._file_path = file_path
        self._knowledge_type = knowledge_type

    @classmethod
    def create(
        cls,
        datasource: str = "",
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
    ):
        """Create knowledge from file path, url or text.

        Args:
             datasource: path of the file to convert
             knowledge_type: type of knowledge

        Examples:
            .. code-block:: python

                from dbgpt.rag.knowledge.factory import KnowledgeFactory

                url_knowlege = KnowledgeFactory.create(
                    datasource="https://www.baidu.com", knowledge_type=KnowledgeType.URL
                )
                doc_knowlege = KnowledgeFactory.create(
                    datasource="path/to/document.pdf",
                    knowledge_type=KnowledgeType.DOCUMENT,
                )

        """
        match knowledge_type:
            case KnowledgeType.DOCUMENT:
                return cls.from_file_path(
                    file_path=datasource, knowledge_type=knowledge_type
                )
            case KnowledgeType.URL:
                return cls.from_url(url=datasource, knowledge_type=knowledge_type)
            case KnowledgeType.TEXT:
                return cls.from_text(text=datasource, knowledge_type=knowledge_type)
            case _:
                raise Exception(f"Unsupported knowledge type '{knowledge_type}'")

    @classmethod
    def from_file_path(
        cls,
        file_path: str = "",
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
    ) -> Knowledge:
        """Create knowledge from path.

        Args:
            param file_path: path of the file to convert
            param knowledge_type: type of knowledge

        Examples:
            .. code-block:: python

                from dbgpt.rag.knowledge.factory import KnowledgeFactory

                doc_knowlege = KnowledgeFactory.create(
                    datasource="path/to/document.pdf",
                    knowledge_type=KnowledgeType.DOCUMENT,
                )
        """
        factory = cls(file_path=file_path, knowledge_type=knowledge_type)
        return factory._select_document_knowledge(
            file_path=file_path, knowledge_type=knowledge_type
        )

    @staticmethod
    def from_url(
        url: str = "",
        knowledge_type: KnowledgeType = KnowledgeType.URL,
    ) -> Knowledge:
        """Create knowledge from url.

        Args:
            param url: url of the file to convert
            param knowledge_type: type of knowledge

        Examples:
            .. code-block:: python

                from dbgpt.rag.knowledge.factory import KnowledgeFactory

                url_knowlege = KnowledgeFactory.create(
                    datasource="https://www.baidu.com", knowledge_type=KnowledgeType.URL
                )
        """
        return URLKnowledge(
            url=url,
            knowledge_type=knowledge_type,
        )

    @staticmethod
    def from_text(
        text: str = "",
        knowledge_type: KnowledgeType = KnowledgeType.TEXT,
    ) -> Knowledge:
        """Create knowledge from text.

        Args:
            param text: text to convert
            param knowledge_type: type of knowledge
        """
        return StringKnowledge(
            text=text,
            knowledge_type=knowledge_type,
        )

    def _select_document_knowledge(self, **kwargs):
        """Select document knowledge from file path."""
        extension = self._file_path.rsplit(".", 1)[-1]
        knowledge_classes = self._get_knowledge_subclasses()
        implementation = None
        for cls in knowledge_classes:
            if cls.document_type() and cls.document_type().value == extension:
                implementation = cls(**kwargs)
        if implementation is None:
            raise Exception(f"Unsupported knowledge document type '{extension}'")
        return implementation

    @classmethod
    def all_types(cls):
        """Get all knowledge types."""
        return [knowledge.type().value for knowledge in cls._get_knowledge_subclasses()]

    @classmethod
    def subclasses(cls) -> List["Type[Knowledge]"]:
        """Get all knowledge subclasses."""
        return cls._get_knowledge_subclasses()

    @staticmethod
    def _get_knowledge_subclasses() -> List["Type[Knowledge]"]:
        """Get all knowledge subclasses."""
        from dbgpt.rag.knowledge.base import Knowledge  # noqa: F401
        from dbgpt.rag.knowledge.csv import CSVKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.datasource import DatasourceKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.docx import DocxKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.html import HTMLKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.markdown import MarkdownKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.pdf import PDFKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.pptx import PPTXKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.string import StringKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.txt import TXTKnowledge  # noqa: F401
        from dbgpt.rag.knowledge.url import URLKnowledge  # noqa: F401

        return Knowledge.__subclasses__()
