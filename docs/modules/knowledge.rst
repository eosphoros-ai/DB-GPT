Knowledge
---------

| As the knowledge base is currently the most significant user demand scenario, we natively support the construction and processing of knowledge bases. At the same time, we also provide multiple knowledge base management strategies in this project, such as pdf knowledge,md knowledge, txt knowledge, word knowledge, ppt knowledge:

We currently support many document formats: raw text, txt, pdf, md, html, doc, ppt, and url.


**Create your own knowledge repository**

1.prepare

We currently support many document formats: raw text, txt, pdf, md, html, doc, ppt, and url.

before execution:

::

    python -m spacy download zh_core_web_sm

2.Update your .env, set your vector store type, VECTOR_STORE_TYPE=Chroma
(now only support Chroma and Milvus, if you set Milvus, please set MILVUS_URL and MILVUS_PORT)

3.init Url Type EmbeddingEngine api and embedding your document into vector store in your code.

::

    url = "https://db-gpt.readthedocs.io/en/latest/getting_started/getting_started.html"
    embedding_model = "text2vec"
    vector_store_config = {
            "vector_store_name": your_name,
        }
    embedding_engine = EmbeddingEngine(
                        knowledge_source=url,
                        knowledge_type=KnowledgeType.URL.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config)
    embedding_engine.knowledge_embedding()

4.init Document Type EmbeddingEngine api and embedding your document into vector store in your code.
Document type can be .txt, .pdf, .md, .doc, .ppt.

::

    document_path = "your_path/test.md"
    embedding_model = "text2vec"
    vector_store_config = {
            "vector_store_name": your_name,
        }
    embedding_engine = EmbeddingEngine(
                        knowledge_source=document_path,
                        knowledge_type=KnowledgeType.DOCUMENT.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config)
    embedding_engine.knowledge_embedding()

5.init TEXT Type EmbeddingEngine api and embedding your document into vector store in your code.

::

    raw_text = "a long passage"
    embedding_model = "text2vec"
    vector_store_config = {
            "vector_store_name": your_name,
        }
    embedding_engine = EmbeddingEngine(
                        knowledge_source=raw_text,
                        knowledge_type=KnowledgeType.TEXT.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config)
    embedding_engine.knowledge_embedding()

4.similar search based on your knowledge base.
::
    query = "please introduce the oceanbase"
    topk = 5
    docs = embedding_engine.similar_search(query, topk)

Note that the default vector model used is text2vec-large-chinese (which is a large model, so if your personal computer configuration is not enough, it is recommended to use text2vec-base-chinese). Therefore, ensure that you download the model and place it in the models directory.

- `pdf_embedding <./knowledge/pdf_embedding.html>`_: supported pdf embedding.


.. toctree::
   :maxdepth: 2
   :caption: Knowledge
   :name: pdf_embedding
   :hidden:

   ./knowledge/pdf/pdf_embedding.md
   ./knowledge/markdown/markdown_embedding.md
   ./knowledge/word/word_embedding.md
   ./knowledge/url/url_embedding.md
   ./knowledge/ppt/ppt_embedding.md