# from langchain.embeddings import HuggingFaceEmbeddings
# from langchain.vectorstores import Milvus
# from pymilvus import Collection,utility
# from pymilvus import datasource, DataType, FieldSchema, CollectionSchema
#
# # milvus = datasource.connect(
# #   alias="default",
# #   host='localhost',
# #   port="19530"
# # )
# # collection = Collection("book")
#
#
# # Get an existing collection.
# # collection.load()
# #
# # search_params = {"metric_type": "L2", "params": {}, "offset": 5}
# #
# # results = collection.search(
# # 	data=[[0.1, 0.2]],
# # 	anns_field="book_intro",
# # 	param=search_params,
# # 	limit=10,
# # 	expr=None,
# # 	output_fields=['book_id'],
# # 	consistency_level="Strong"
# # )
# #
# # # get the IDs of all returned hits
# # results[0].ids
# #
# # # get the distances to the query vector from all returned hits
# # results[0].distances
# #
# # # get the value of an output field specified in the search request.
# # # vector fields are not supported yet.
# # hit = results[0][0]
# # hit.entity.get('title')
#
# # milvus = datasource.connect(
# #   alias="default",
# #   host='localhost',
# #   port="19530"
# # )
# from dbgpt.vector_store.milvus_store import MilvusStore
#
# data = ["aaa", "bbb"]
# model_name = "xx/all-MiniLM-L6-v2"
# embeddings = HuggingFaceEmbeddings(model_name=model_name)
#
# # text_embeddings = Text2Vectors()
# mivuls = MilvusStore(cfg={"url": "127.0.0.1", "port": "19530", "alias": "default", "table_name": "test_k"})
#
# mivuls.insert(["textc","tezt2"])
# print("success")
# ct
# # mivuls.from_texts(texts=data, embedding=embeddings)
# #     docs,
# #     embedding=embeddings,
# #     connection_args={"host": "127.0.0.1", "port": "19530", "alias": "default"}
# # )
