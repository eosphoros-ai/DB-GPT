VectorConnector
---------

**VectorConnector Introduce**

vector knowledge base is a method of mapping words in language to a high-dimensional vector space. In the vector space, each word is represented as a vector that contains many numerical features, which represent the relationship between the word and other words. This mapping is a clustering technique, and the semantic relationship between words can be calculated by computing the differences between their vectors in the vector space. Vector knowledge bases can be used for natural language processing tasks such as sentiment analysis, text classification, and machine translation. Common vector knowledge bases include Word2Vec, GloVe, and FastText. The training of these vector knowledge bases usually requires a large corpus and computing resources to complete.

VectorConnector is a vector database connection adapter that allows you to connect different vector databases and abstracts away implementation differences and underlying details of different vector data. For example, it can be used to connect to databases such as Milvus, Chroma, Elasticsearch, and Weaviate.

DB-GPT VectorConnector currently support Chroma(Default), Milvus(>2.1), Weaviate vector database.

If you want to change vector db, Update your .env, set your vector store type, VECTOR_STORE_TYPE=Chroma (now only support Chroma, Milvus(>2.1) and Weaviate, if you set Milvus, please set MILVUS_URL and MILVUS_PORT)

::

    #*******************************************************************#
    #**                  VECTOR STORE SETTINGS                       **#
    #*******************************************************************#
    VECTOR_STORE_TYPE=Chroma
    #MILVUS_URL=127.0.0.1
    #MILVUS_PORT=19530
    #MILVUS_USERNAME
    #MILVUS_PASSWORD
    #MILVUS_SECURE=
    #WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network


- `chroma <./vector/chroma.html>`_: supported chroma vector database.
- `milvus <./vector/milvus.html>`_: supported milvus vector database.
- `weaviate <./vector/weaviate.html>`_: supported weaviate vector database.


.. toctree::
   :maxdepth: 2
   :caption: VectorConnector
   :name: chroma
   :hidden:

   ./vector/chroma/chroma.md
   ./vector/milvus/milvus.md
   ./vector/weaviate/weaviate.md