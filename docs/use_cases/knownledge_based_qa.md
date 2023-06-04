# Knownledge based qa

Chat with your own knowledge is a very interesting thing. In the usage scenarios of this chapter, we will introduce how to build your own knowledge base through the knowledge base API. Firstly, building a knowledge store can currently be initialized by executing "python tool/knowledge_init.py" to initialize the content of your own knowledge base, which was introduced in the previous knowledge base module. Of course, you can also call our provided knowledge embedding API to store knowledge.


We currently support four document formats: txt, pdf, url, and md.
```
vector_store_config = {
    "vector_store_name": name
}

file_path = "your file path"

knowledge_embedding_client = KnowledgeEmbedding(file_path=file_path, model_name=LLM_MODEL_CONFIG["text2vec"],local_persist=False, vector_store_config=vector_store_config)

knowledge_embedding_client.knowledge_embedding()

```

Now we currently support vector databases:  Chroma (default) and Milvus. You can switch between them by modifying the "VECTOR_STORE_TYPE" field in the .env file. 
```
#*******************************************************************#
#**                  VECTOR STORE SETTINGS                       **#
#*******************************************************************#
VECTOR_STORE_TYPE=Chroma
#MILVUS_URL=127.0.0.1
#MILVUS_PORT=19530
```


Below is an example of using the knowledge base API to query knowledge:

```
vector_store_config = {
    "vector_store_name": name
}

query = "your query"

knowledge_embedding_client = KnowledgeEmbedding(file_path="", model_name=LLM_MODEL_CONFIG["text2vec"], local_persist=False, vector_store_config=vector_store_config)

knowledge_embedding_client.similar_search(query, 10)
```