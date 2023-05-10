from langchain.vectorstores import Milvus
from pymilvus import Collection,utility
from pymilvus import connections, DataType, FieldSchema, CollectionSchema
from pilot.source_embedding.Text2Vectors import Text2Vectors

# milvus = connections.connect(
#   alias="default",
#   host='localhost',
#   port="19530"
# )
# collection = Collection("book")


# Get an existing collection.
# collection.load()
#
# search_params = {"metric_type": "L2", "params": {}, "offset": 5}
#
# results = collection.search(
# 	data=[[0.1, 0.2]],
# 	anns_field="book_intro",
# 	param=search_params,
# 	limit=10,
# 	expr=None,
# 	output_fields=['book_id'],
# 	consistency_level="Strong"
# )
#
# # get the IDs of all returned hits
# results[0].ids
#
# # get the distances to the query vector from all returned hits
# results[0].distances
#
# # get the value of an output field specified in the search request.
# # vector fields are not supported yet.
# hit = results[0][0]
# hit.entity.get('title')

milvus = connections.connect(
  alias="default",
  host='localhost',
  port="19530"
)
data = ["aaa", "bbb"]
text_embeddings = Text2Vectors()
mivuls = Milvus(collection_name='document', embedding_function= text_embeddings, connection_args={"host": "127.0.0.1", "port": "19530", "alias":"default"}, text_field="")

mivuls.from_texts(texts=data, embedding=text_embeddings)
#     docs,
#     embedding=embeddings,
#     connection_args={"host": "127.0.0.1", "port": "19530", "alias": "default"}
# )