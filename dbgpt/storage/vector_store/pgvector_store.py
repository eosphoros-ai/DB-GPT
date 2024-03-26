"""Postgres vector store."""
from dbgpt._private.config import Config
from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk
import logging
from typing import Any, List
from sqlalchemy import create_engine

from dbgpt.rag.chunk import Chunk
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig

logger = logging.getLogger(__name__)

CFG = Config()


class PGVectorConfig(VectorStoreConfig):
    """PG vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    connection_string: str = Field(
        default=None,
        description="the connection string of vector store, if not set, will use the "
        "default connection string.",
    )


class PGVectorStore(VectorStoreBase):
    """PG vector store.

    To use this, you should have the ``pgvector`` python package installed.
    """

    def __init__(self, vector_store_config: PGVectorConfig) -> None:
        """Create a PGVectorStore instance."""
        from langchain.vectorstores import PGVector

        self.connection_string = vector_store_config.connection_string
        self.embeddings = vector_store_config.embedding_fn
        self.collection_name = vector_store_config.name

        self.vector_store_client = PGVector(
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
            connection_string=self.connection_string,
        )

    def similar_search(self, text, topk, **kwargs: Any) -> None:
        """Perform similar search in PGVector."""
        return self.vector_store_client.similarity_search(text, topk)

    def vector_name_exists(self):
        try:
            from sqlalchemy.sql import text
            engine = create_engine(self.connection_string)
            """Check if vector name exists."""
            # ATL
            with engine.connect() as connection:
                # 编写你的 SQL 查询
                sql_query = text("""
                       select
                           count(1)
                       from
                           {langchain_pg_embedding}
                       where
                           collection_id = (
                           select
                               distinct(uuid)
                           from
                               {collection_store}
                           where
                               name = '{collection_name}'
                           limit 1)""".format(
                    langchain_pg_embedding=self.vector_store_client.EmbeddingStore.__tablename__,
                    collection_store=self.vector_store_client.CollectionStore.__tablename__,
                    collection_name=self.collection_name))

                # 执行查询，并传入参数
                result = connection.execute(sql_query)
                num_docs = list(result)[0][0]
                print('num_docs',num_docs)
            if num_docs > 0:
                return True
            else:
                return False
        except Exception as e:
            logger.error("vector_name_exists error", e.message)
            return False

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to PGVector.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """
        lc_documents = [Chunk.chunk2langchain(chunk) for chunk in chunks]
        return self.vector_store_client.from_documents(embedding=self.embeddings,
                                                       documents=lc_documents,
                                                       collection_name=self.collection_name,
                                                       connection_string=self.connection_string)

    def delete_vector_name(self, vector_name: str):
        """Delete vector by name.

        Args:
            vector_name(str): vector name.
        """
        return self.vector_store_client.delete_collection()

    def delete_by_ids(self, ids: str):
        """Delete vector by ids.

        Args:
            ids(str): vector ids, separated by comma.
        """
        return self.vector_store_client.delete(ids)

    def similar_search_with_scores(self, text, topk, score_threshold) -> List[Chunk]:
        """
        Chroma similar_search_with_score.
        Return docs and relevance scores in the range [0, 1].
        Args:
            text(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        """
        logger.info("ChromaStore similar search with scores")
        docs_and_scores = (
            self.vector_store_client.similarity_search_with_score(
                query=text, k=topk, filter=score_threshold
            )
        )
        return [
            Chunk(content=doc.page_content, metadata=doc.metadata, score=score)
            for doc, score in docs_and_scores
        ]

    def dbname_dbm25(self) -> List:
        """
        Chroma similar_search_with_score.
        Return docs and relevance scores in the range [0, 1].
        Args:
            text(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs,0 is dissimilar, 1 is most similar.
        """
        from sqlalchemy.sql import text
        engine = create_engine(self.connection_string)
        with engine.connect() as connection:
            # 编写你的 SQL 查询
            _sql = '''
            select
                lpe.document
            from
                langchain_pg_collection lpc
            join langchain_pg_embedding lpe on
                lpc.uuid = lpe.collection_id
            where
                lpc.name = '{collection_name}' 
            '''
            sql_query = text(_sql.format(collection_name=self.collection_name))

            # 执行查询，并传入参数
            result = connection.execute(sql_query)
            num_docs = list(i[0] for i in result)
        return num_docs

if __name__ == '__main__':
    from dbgpt.storage.vector_store.connector import VectorStoreConnector

    vector_store_config = PGVectorConfig(
        connection_string='postgresql+psycopg2://fastgpt:1234@172.23.10.249:8100/newfastgpt',
        name='hr_en_profile')
    vector_store_connector = VectorStoreConnector(vector_store_type='PGVector', vector_store_config=vector_store_config)
    pgvs = PGVectorStore(vector_store_config)
    vsc = pgvs.vector_store_client
    print(vsc.CollectionStore.__tablename__)
    print(pgvs.vector_name_exists())
