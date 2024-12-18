# Hybrid Knowledge Process Workflow
# Introduction
At present, the DB-GPT knowledge base provides knowledge processing capabilities such as `document uploading` ->` parsing` ->` chunking` ->` Embedding` -> `Knowledge Graph triple extraction `-> `vector database storage` ->  `graph database storage`, but it does not have the ability to extract complex information from documents, including vector extraction and Knowledge Graph extraction from document blocks at the same time. The hybrid knowledge processing template defines complex knowledge processing workflow, it also supports document vector extraction, Keyword extraction and Knowledge Graph extraction.

# Applicable Scenarios 
+ It is not limited to the traditional, single knowledge processing process (only Embedding processing or knowledge graph extraction processing), knowledge processing workflow implements Embedding and Knowledge Graph extraction at the same time, as a mixed knowledge recall retrieval data storage. 
+ Users can tailor and add existing knowledge processing processes based on their own business scenarios.

# How to use 
+ Enter the AWEL interface and add a workflow

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ Import Knowledge Processing Template

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734357236704-5a15be65-3d11-4406-98d7-efb82e5142dc.png)

+ Adjust parameters and save

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734355123947-3e252e59-2b2a-4bca-adef-13a93ee6cdf3.png)

    - `Document knowledge loading operator `: Knowledge loading factory, by loading the specified document type, find the corresponding document processor for document content parsing. 
    - `Document Chunk slicing operator `: Slice the loaded document content according to the specified slicing parameters. 
    - `Knowledge Processing branch operator `: You can connect different knowledge processing processes, including knowledge map processing processes, vector processing processes, and keyword processing processes. 
    - `Vector storage machining operator `: You can connect different vector databases for vector storage, and you can also connect different Embedding models and services for vector extraction. 
    - `Knowledge Graph processing operator `: You can connect different knowledge graph processing operators, including native knowledge graph processing operators and community summary Knowledge Graph processing operators. You can also specify different graph databases for storage. Currently, TuGraph databases are supported. 
    - `Result aggregation operator `: Summarize the results of vector extraction and Knowledge Graph extraction.
+ Register Post as http request

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/hybrid/process' \
--header 'Content-Type: application/json' \
--data-raw '{}'
```

```bash
[
    "async persist vector store success 1 chunks.",
    "async persist graph store success 1 chunks."
]
```





