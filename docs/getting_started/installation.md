# Installation
DB-GPT provides a third-party Python API package that you can integrate into your own code.

### Installation from Pip

You can simply pip install:
```bash
pip install -i https://pypi.org/simple/ db-gpt==0.3.0
```

```{tip}
Notice:make sure python>=3.10
```

### Environment Setup

By default, if you use the EmbeddingEngine api

you will prepare embedding models from huggingface

```{tip}
Notice make sure you have install git-lfs
```

```bash
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```
version:
- db-gpt0.3.0
  - [embedding_engine api](https://db-gpt.readthedocs.io/en/latest/modules/knowledge.html)
  - [multi source embedding](https://db-gpt.readthedocs.io/en/latest/modules/knowledge/pdf/pdf_embedding.html)
  - [vector connector](https://db-gpt.readthedocs.io/en/latest/modules/vector.html)

