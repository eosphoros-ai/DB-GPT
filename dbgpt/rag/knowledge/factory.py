from typing import Optional

from dbgpt.rag.knowledge.base import KnowledgeType, Knowledge
from dbgpt.rag.knowledge.csv import CSVKnowledge
from dbgpt.rag.knowledge.docx import DocxKnowledge
from dbgpt.rag.knowledge.markdown import MarkdownKnowledge
from dbgpt.rag.knowledge.pdf import PDFKnowledge
from dbgpt.rag.knowledge.string import StringKnowledge
from dbgpt.rag.knowledge.txt import TXTKnowledge
from dbgpt.rag.knowledge.url import URLKnowledge

KnowledgeTypeMapping = {
    ".pdf": (PDFKnowledge, {}),
    ".txt": (TXTKnowledge, {}),
    ".md": (MarkdownKnowledge, {}),
    ".docx": (DocxKnowledge, {}),
    ".csv": (CSVKnowledge, {}),
    ".xlsx": (CSVKnowledge, {}),
}


class KnowledgeFactory:
    """Knowledge Factory to create knowledge from file path and url"""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
    ):
        self._file_path = file_path
        self._knowledge_type = knowledge_type

    @classmethod
    def from_file_path(
        cls,
        file_path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
    ) -> Knowledge:
        """Create knowledge from path"""
        factory = cls(file_path=file_path, knowledge_type=knowledge_type)
        return factory._select_document_knowledge()

    @staticmethod
    def from_url(
        url: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.URL,
    ) -> Knowledge:
        """Create knowledge from url"""
        return URLKnowledge(
            url=url,
            knowledge_type=knowledge_type,
        )

    @staticmethod
    def from_text(
        text: str = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.TEXT,
    ) -> Knowledge:
        """Create knowledge from text"""
        return StringKnowledge(
            text=text,
            knowledge_type=knowledge_type,
        )

    def _select_document_knowledge(self):
        """Select document knowledge from file path"""
        extension = "." + self._file_path.rsplit(".", 1)[-1]
        if extension in KnowledgeTypeMapping:
            knowledge_class, knowledge_args = KnowledgeTypeMapping[extension]
            knowledge = knowledge_class(
                self._file_path,
                **knowledge_args,
            )
            return knowledge
        raise ValueError(f"Unsupported knowledge document type '{extension}'")
