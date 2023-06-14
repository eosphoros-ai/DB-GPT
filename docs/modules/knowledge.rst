Knowledge
---------

| As the knowledge base is currently the most significant user demand scenario, we natively support the construction and processing of knowledge bases. At the same time, we also provide multiple knowledge base management strategies in this project, such as pdf knowledge,md knowledge, txt knowledge, word knowledge, ppt knowledge:


**Create your own knowledge repository**

1.Place personal knowledge files or folders in the pilot/datasets directory.

We currently support many document formats: txt, pdf, md, html, doc, ppt, and url.

before execution:  python -m spacy download zh_core_web_sm

2.Update your .env, set your vector store type, VECTOR_STORE_TYPE=Chroma
(now only support Chroma and Milvus, if you set Milvus, please set MILVUS_URL and MILVUS_PORT)

2.Run the knowledge repository script in the tools directory.

python tools/knowledge_init.py
note : --vector_name : your vector store name  default_value:default

3.Add the knowledge repository in the interface by entering the name of your knowledge repository (if not specified, enter "default") so you can use it for Q&A based on your knowledge base.

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