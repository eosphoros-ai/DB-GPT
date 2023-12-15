from enum import Enum

from dbgpt.rag.embedding_engine.csv_embedding import CSVEmbedding
from dbgpt.rag.embedding_engine.markdown_embedding import MarkdownEmbedding
from dbgpt.rag.embedding_engine.pdf_embedding import PDFEmbedding
from dbgpt.rag.embedding_engine.ppt_embedding import PPTEmbedding
from dbgpt.rag.embedding_engine.string_embedding import StringEmbedding
from dbgpt.rag.embedding_engine.url_embedding import URLEmbedding
from dbgpt.rag.embedding_engine.word_embedding import WordEmbedding


def get_knowledge_embedding(
    knowledge_type,
    knowledge_source,
    vector_store_config=None,
    source_reader=None,
    text_splitter=None,
):
    match knowledge_type:
        case KnowledgeType.DOCUMENT.value:
            extension = "." + knowledge_source.rsplit(".", 1)[-1]
            if extension in DocumentEmbeddingType:
                knowledge_class, knowledge_args = DocumentEmbeddingType[extension]
                embedding = knowledge_class(
                    knowledge_source,
                    vector_store_config=vector_store_config,
                    source_reader=source_reader,
                    text_splitter=text_splitter,
                    **knowledge_args,
                )
                return embedding
            raise ValueError(f"Unsupported knowledge document type '{extension}'")
        case KnowledgeType.URL.value:
            embedding = URLEmbedding(
                file_path=knowledge_source,
                vector_store_config=vector_store_config,
                source_reader=source_reader,
                text_splitter=text_splitter,
            )
            return embedding
        case KnowledgeType.TEXT.value:
            embedding = StringEmbedding(
                file_path=knowledge_source,
                vector_store_config=vector_store_config,
                source_reader=source_reader,
                text_splitter=text_splitter,
            )
            return embedding
