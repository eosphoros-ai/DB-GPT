# Knownledge based qa

Chat with your own knowledge is a very interesting thing. In the usage scenarios of this chapter, we will introduce how to build your own knowledge base through the knowledge base API. Firstly, building a knowledge store can currently be initialized by executing "python tool/knowledge_init.py" to initialize the content of your own knowledge base, which was introduced in the previous knowledge base module. Of course, you can also call our provided knowledge embedding API to store knowledge.


We currently support many document formats: txt, pdf, md, html, doc, ppt, and url.
```
vector_store_config = {
    "vector_store_name": name
}

file_path = "your file path"

embedding_engine = EmbeddingEngine(file_path=file_path, model_name=LLM_MODEL_CONFIG["text2vec"], vector_store_config=vector_store_config)

embedding_engine.knowledge_embedding()

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

embedding_engine = EmbeddingEngine(knowledge_source=url, knowledge_type=KnowledgeType.URL.value, model_name=embedding_model, vector_store_config=vector_store_config)

embedding_engine.similar_search(query, 10)
```