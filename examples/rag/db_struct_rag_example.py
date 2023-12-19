from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
from dbgpt.serve.rag.assembler.db_struct import DBStructAssembler
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig


def _create_temporary_connection():
    """Create a temporary database connection for testing."""
    connect = SQLiteTempConnect.create_temporary_db()
    connect.create_temp_tables(
        {
            "user": {
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "name": "TEXT",
                    "age": "INTEGER",
                },
                "data": [
                    (1, "Tom", 10),
                    (2, "Jerry", 16),
                    (3, "Jack", 18),
                    (4, "Alice", 20),
                    (5, "Bob", 22),
                ],
            }
        }
    )
    return connect


if __name__ == "__main__":
    connection = _create_temporary_connection()
    vector_store_config = ChromaVectorConfig(name="vector_store_name")
    embedding_model_path = "{your_embedding_model_path}"
    vector_connector = VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=vector_store_config,
    )
    assembler = DBStructAssembler.load_from_connection(
        connection=connection,
        embedding_model=embedding_model_path,
    )
    assembler.persist()
    # get db struct retriever
    retriever = assembler.as_retriever(top_k=3)
    chunks = retriever.retrieve("show columns from table")
    print(f"db struct rag example results:{[chunk.content for chunk in chunks]}")