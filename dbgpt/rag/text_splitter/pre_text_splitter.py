from typing import Iterable, List

from dbgpt.rag.chunk import Document, Chunk
from dbgpt.rag.text_splitter.text_splitter import TextSplitter


def _single_document_split(
    document: Document, pre_separator: str
) -> Iterable[Document]:
    content = document.content
    for i, content in enumerate(content.split(pre_separator)):
        metadata = document.metadata.copy()
        if "source" in metadata:
            metadata["source"] = metadata["source"] + "_pre_split_" + str(i)
        yield Chunk(content=content, metadata=metadata)


class PreTextSplitter(TextSplitter):
    """Split text by pre separator"""

    def __init__(self, separator: str, text_splitter_impl: TextSplitter):
        """Initialize with Knowledge arguments.
        Args:
            pre_separator: pre separator
            text_splitter_impl: text splitter impl
        """
        self.pre_separator = separator
        self._impl = text_splitter_impl

    def split_text(self, text: str) -> List[str]:
        """Split text by pre separator"""
        return self._impl.split_text(text)

    def split_documents(self, documents: Iterable[Document]) -> List[Chunk]:
        """Split documents by pre separator"""

        def generator() -> Iterable[Document]:
            for doc in documents:
                yield from _single_document_split(doc, pre_separator=self.pre_separator)

        return self._impl.split_documents(generator())