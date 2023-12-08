from typing import Iterable, List
from langchain.schema import Document
from langchain.text_splitter import TextSplitter


def _single_document_split(
    document: Document, pre_separator: str
) -> Iterable[Document]:
    page_content = document.page_content
    for i, content in enumerate(page_content.split(pre_separator)):
        metadata = document.metadata.copy()
        if "source" in metadata:
            metadata["source"] = metadata["source"] + "_pre_split_" + str(i)
        yield Document(page_content=content, metadata=metadata)


class PreTextSplitter(TextSplitter):
    def __init__(self, pre_separator: str, text_splitter_impl: TextSplitter):
        self.pre_separator = pre_separator
        self._impl = text_splitter_impl

    def split_text(self, text: str) -> List[str]:
        return self._impl.split_text(text)

    def split_documents(self, documents: Iterable[Document]) -> List[Document]:
        def generator() -> Iterable[Document]:
            for doc in documents:
                yield from _single_document_split(doc, pre_separator=self.pre_separator)

        return self._impl.split_documents(generator())
