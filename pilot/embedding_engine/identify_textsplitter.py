from typing import Iterable, List
from langchain.schema import Document
from langchain.text_splitter import TextSplitter


class IdentifyTextSplitter(TextSplitter):
    def __init__(self, identify_separators: List[str] = ["\n\n"]):
        self.identify_separators = ["\n\n"] if identify_separators is None else identify_separators

    def split_text(self, text: str) -> List[str]:
        split_texts = [text]
        for identify_separator in self.identify_separators:
            tmp_result = []
            for split_text in split_texts:
                tmp_result.extend(split_text.split(identify_separator))
            split_texts = tmp_result
        return split_texts

    def split_documents(self, documents: Iterable[Document]) -> List[Document]:
        """
          documents = [Document(page_content=text, metadata=metadata)]
        """
        chunks = []
        for doc in documents:
            split_docs = self.split_text(doc.page_content)
            chunks.extend([Document(page_content=split_doc, metadata=doc.metadata) for split_doc in split_docs])
        return chunks


def split_text(text: str, identify_separators: List[str] = ["\n\n"]) -> List[str]:
    split_texts = [text]
    for identify_separator in identify_separators:
        tmp_result = []
        for split_text in split_texts:
            tmp_result.extend(split_text.split(identify_separator))
        split_texts = tmp_result
    return split_texts
