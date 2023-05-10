from random import random

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Milvus
from langchain.document_loaders import WebBaseLoader
from langchain.text_splitter import CharacterTextSplitter
from pymilvus import connections, DataType, FieldSchema, CollectionSchema
from pymilvus import Collection



from pilot.source_embedding.text_to_vector import TextToVector


loader = WebBaseLoader([
    "https://milvus.io/docs/overview.md",
])

docs = loader.load()

# Split the documents into smaller chunks
# text_splitter = CharacterTextSplitter(chunk_size=1024, chunk_overlap=0)
# docs = text_splitter.split_documents(docs)

embeddings = TextToVector.textToVector(docs[0].page_content)

milvus = connections.connect(
  alias="default",
  host='localhost',
  port="19530"
)

# collection = Collection("test_book")



# data = [{"doc_id": 11011, "content": 11011, "title": 11011,  "vector": embeddings[0]}]
# # collection = Collection("document")
#
# # collection.insert(data=data)
# entities = [
#     {
#         'doc_id': d['doc_id'],
#         'vector': d['vector'],
#         'content': d['content'],
#         'title': d['titlseae'],
#         "type": DataType.FLOAT_VECTOR
#     } for d in data
# ]
#
# milvus.insert(collection_name="document", entities=entities)
# print("success")
# 定义集合的字段
# fields = [
#     FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR),
#     FieldSchema(name="age", dtype=DataType.INT32),
#     FieldSchema(name="gender", dtype=DataType.STRING),
#     FieldSchema(name="id", dtype=DataType.INT64)  # 添加主键字段
# ]

# book_id = FieldSchema(
#   name="book_id",
#   dtype=DataType.INT64,
#   is_primary=True,
# )
# book_name = FieldSchema(
#   name="book_name",
#   dtype=DataType.BINARY_VECTOR,
#   max_length=200,
# )
# word_count = FieldSchema(
#   name="word_count",
#   dtype=DataType.INT64,
# )
# book_intro = FieldSchema(
#   name="book_intro",
#   dtype=DataType.FLOAT_VECTOR,
#   dim=2
# )
# schema = CollectionSchema(
#   fields=[book_id, book_name, word_count, book_intro],
#   description="Test book search"
# )
collection_name = "test_book"

collection = Collection(
    name=collection_name,
    schema=schema,
    using='default',
    shards_num=2
    )
# 插入数据
# entities = [[
#     {"book_id": 30, "book_intro": [0.1, 0.2], "word_count": 1},
#     {"book_id": 25, "book_intro": [0.1, 0.2], "word_count": 2},
#     {"book_id": 40, "book_intro": [0.1, 0.2], "word_count": 3}
# ]]

entities = [[30, 25, 40], ["test1", "test2", "test3"], [1, 2, 3], [[0.1, 0.2], [0.1, 0.2], [0.1, 0.2]]]

collection.insert(entities)
print("success")

# vector_store = Milvus.from_documents(
#     docs,
#     embedding=embeddings,
#     connection_args={"host": "127.0.0.1", "port": "19530", "alias": "default"}
# )