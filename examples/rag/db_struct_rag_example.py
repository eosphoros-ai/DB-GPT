from dbgpt.datasource.rdbms.conn_sqlite import SQLiteTempConnect
from dbgpt.rag.embedding.embedding_factory import DefaultEmbeddingFactory
from dbgpt.serve.rag.assembler.db_struct import DBStructAssembler
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

"""DB struct rag example.
    pre-requirements:
    set your embedding model path in your example code.
    ```
    embedding_model_path = "{your_embedding_model_path}"
    ```
    
    Examples:
        ..code-block:: shell
            python examples/rag/db_struct_rag_example.py
"""


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

    embedding_model_path = "{your_embedding_model_path}"
    vector_persist_path = "{your_persist_path}"
    embedding_fn = DefaultEmbeddingFactory(
        default_model_name=embedding_model_path
    ).create()
    vector_connector = VectorStoreConnector.from_default(
        "Chroma",
        vector_store_config=ChromaVectorConfig(
            name="vector_name",
            persist_path=vector_persist_path,
        ),
        embedding_fn=embedding_fn,
    )
    assembler = DBStructAssembler.load_from_connection(
        connection=connection,
        vector_store_connector=vector_connector,
    )
    assembler.persist()
    # get db struct retriever
    retriever = assembler.as_retriever(top_k=1)
    chunks = retriever.retrieve("show columns from user")
    print(f"db struct rag example results:{[chunk.content for chunk in chunks]}")
