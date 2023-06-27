from enum import Enum

from pilot.embedding_engine.csv_embedding import CSVEmbedding
from pilot.embedding_engine.markdown_embedding import MarkdownEmbedding
from pilot.embedding_engine.pdf_embedding import PDFEmbedding
from pilot.embedding_engine.ppt_embedding import PPTEmbedding
from pilot.embedding_engine.string_embedding import StringEmbedding
from pilot.embedding_engine.url_embedding import URLEmbedding
from pilot.embedding_engine.word_embedding import WordEmbedding

DocumentEmbeddingType = {
    ".txt": (MarkdownEmbedding, {}),
    ".md": (MarkdownEmbedding, {}),
    ".pdf": (PDFEmbedding, {}),
    ".doc": (WordEmbedding, {}),
    ".docx": (WordEmbedding, {}),
    ".csv": (CSVEmbedding, {}),
    ".ppt": (PPTEmbedding, {}),
    ".pptx": (PPTEmbedding, {}),
}


class KnowledgeType(Enum):
    DOCUMENT = "DOCUMENT"
    URL = "URL"
    TEXT = "TEXT"
    OSS = "OSS"
    NOTION = "NOTION"


def get_knowledge_embedding(knowledge_type, knowledge_source, vector_store_config):
    match knowledge_type:
        case KnowledgeType.DOCUMENT.value:
            extension = "." + knowledge_source.rsplit(".", 1)[-1]
            if extension in DocumentEmbeddingType:
                knowledge_class, knowledge_args = DocumentEmbeddingType[extension]
                embedding = knowledge_class(
                    knowledge_source,
                    vector_store_config=vector_store_config,
                    **knowledge_args,
                )
                return embedding
            raise ValueError(f"Unsupported knowledge document type '{extension}'")
        case KnowledgeType.URL.value:
            embedding = URLEmbedding(
                file_path=knowledge_source,
                vector_store_config=vector_store_config,
            )
            return embedding
        case KnowledgeType.TEXT.value:
            embedding = StringEmbedding(
                file_path=knowledge_source,
                vector_store_config=vector_store_config,
            )
            return embedding
        case KnowledgeType.OSS.value:
            raise Exception("OSS have not integrate")
        case KnowledgeType.NOTION.value:
            raise Exception("NOTION have not integrate")

        case _:
            raise Exception("unknown knowledge type")
