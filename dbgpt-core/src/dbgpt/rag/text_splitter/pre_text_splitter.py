"""Pre text splitter."""
from typing import Iterable, List

from dbgpt.core import Chunk, Document
from dbgpt.rag.text_splitter.text_splitter import TextSplitter


def _single_document_split(
    document: Document, pre_separator: str
) -> Iterable[Document]:
    origin_content = document.content
    for i, content in enumerate(origin_content.split(pre_separator)):
        metadata = document.metadata.copy()
        if "source" in metadata:
            metadata["source"] = metadata["source"] + "_pre_split_" + str(i)
        yield Chunk(content=content, metadata=metadata)


class PreTextSplitter(TextSplitter):
    """Split text by pre separator."""

    def __init__(self, pre_separator: str, text_splitter_impl: TextSplitter):
        """Create the pre text splitter instance.

        Args:
            pre_separator: pre separator
            text_splitter_impl: text splitter impl
        """
        self.pre_separator = pre_separator
        self._impl = text_splitter_impl

    def split_text(self, text: str, **kwargs) -> List[str]:
        """Split text by pre separator."""
        return self._impl.split_text(text)

    def split_documents(self, documents: Iterable[Document], **kwargs) -> List[Chunk]:
        """Split documents by pre separator."""

        def generator() -> Iterable[Document]:
            for doc in documents:
                yield from _single_document_split(doc, pre_separator=self.pre_separator)

        return self._impl.split_documents(generator())
