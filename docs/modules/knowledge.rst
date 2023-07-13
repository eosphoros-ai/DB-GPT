Knowledge
---------

| As the knowledge base is currently the most significant user demand scenario, we natively support the construction and processing of knowledge bases. At the same time, we also provide multiple knowledge base management strategies in this project, such as pdf knowledge,md knowledge, txt knowledge, word knowledge, ppt knowledge:

We currently support many document formats: raw text, txt, pdf, md, html, doc, ppt, and url.
In the future, we will continue to support more types of knowledge, including audio, video, various databases, and big data sources. Of course, we look forward to your active participation in contributing code.

**Create your own knowledge repository**

1.prepare

We currently support many document formats: TEXT(raw text), DOCUMENT(.txt, .pdf, .md, .doc, .ppt, .html), and URL.

before execution:

::

    pip install  db-gpt -i https://pypi.org/
    python -m spacy download zh_core_web_sm
    from pilot import EmbeddingEngine,KnowledgeType


2.prepare embedding model, you can download from https://huggingface.co/.
Notice you have installed git-lfs.

eg: git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

::

    embedding_model = "your_embedding_model_path/all-MiniLM-L6-v2"

3.prepare vector_store instance and vector store config, now we support Chroma, Milvus and Weaviate.

::

    #Chroma
    vector_store_config = {
        "vector_store_type":"Chroma",
        "vector_store_name":"your_name",#you can define yourself
        "chroma_persist_path":"your_persist_dir"
    }
    #Milvus
    vector_store_config = {
        "vector_store_type":"Milvus",
        "vector_store_name":"your_name",#you can define yourself
        "milvus_url":"your_url",
        "milvus_port":"your_port",
        "milvus_username":"your_username",(optional)
        "milvus_password":"your_password",(optional)
        "milvus_secure":"your_secure"(optional)
    }
    #Weaviate
    vector_store_config = {
        "vector_store_type":"Weaviate",
        "vector_store_name":"your_name",#you can define yourself
        "weaviate_url":"your_url",
        "weaviate_port":"your_port",
        "weaviate_username":"your_username",(optional)
        "weaviate_password":"your_password",(optional)
    }

3.init Url Type EmbeddingEngine api and embedding your document into vector store in your code.

::

    url = "https://db-gpt.readthedocs.io/en/latest/getting_started/getting_started.html"
    embedding_engine = EmbeddingEngine(
                        knowledge_source=url,
                        knowledge_type=KnowledgeType.URL.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config)
    embedding_engine.knowledge_embedding()

If you want to add your source_reader or text_splitter, do this:

::

    url = "https://db-gpt.readthedocs.io/en/latest/getting_started/getting_started.html"

    source_reader = WebBaseLoader(web_path=self.file_path)
    text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=100, chunk_overlap=50
                    )
    embedding_engine = EmbeddingEngine(
                        knowledge_source=url,
                        knowledge_type=KnowledgeType.URL.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config,
                        source_reader=source_reader,
                        text_splitter=text_splitter
                        )


4.init Document Type EmbeddingEngine api and embedding your document into vector store in your code.
Document type can be .txt, .pdf, .md, .doc, .ppt.

::

    document_path = "your_path/test.md"
    embedding_engine = EmbeddingEngine(
                        knowledge_source=document_path,
                        knowledge_type=KnowledgeType.DOCUMENT.value,
                        model_name=embedding_model,
                        vector_store_config=vector_store_config)
    embedding_engine.knowledge_embedding()

5.init TEXT Type EmbeddingEngine api and embedding your document into vector store in your code.

::

    raw_text = "a long passage"
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

- `pdf_embedding <./knowledge/pdf/pdf_embedding.html>`_: supported pdf embedding.
- `markdown_embedding <./knowledge/markdown/markdown_embedding.html>`_: supported markdown embedding.
- `word_embedding <./knowledge/word/word_embedding.html>`_: supported word embedding.
- `url_embedding <./knowledge/url/url_embedding.html>`_: supported url embedding.
- `ppt_embedding <./knowledge/ppt/ppt_embedding.html>`_: supported ppt embedding.
- `string_embedding <./knowledge/string/string_embedding.html>`_: supported raw text embedding.


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
   ./knowledge/string/string_embedding.md