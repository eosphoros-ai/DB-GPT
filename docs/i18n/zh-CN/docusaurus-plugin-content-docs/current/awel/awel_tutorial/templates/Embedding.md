# Embedding Process Workflow 
# Introduction 
the traditional knowledge extraction preparation process of Native RAG aims at the process of turning documents into databases, including reading unstructured documents-&gt; knowledge slices-&gt; document slices turning-&gt; import vector databases. 

# Applicable Scenarios 
+ supports simple intelligent question and answer scenarios and recalls context information through semantic similarity. 
+ Users can cut and add existing embedded processing processes according to their own business scenarios. 

# How to use 
+ enter the AWEL interface and add a workflow 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ import Knowledge Processing Template 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734358060884-672d3157-a2ee-498b-887e-ea51f1caddae.png)

+ adjust parameters and save 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734358170081-32d38282-7765-4bbf-9bf7-c068550907d1.png)

    - `document knowledge loader operator `: Knowledge loading factory, by loading the specified document type, find the corresponding document processor for document content parsing. 
    - `Document Chunk Manager operator `: Slice the loaded document content according to the specified slicing parameters. 
    - `Vector storage machining operator `: You can connect different vector databases for vector storage, and you can also connect different Embedding models and services for vector extraction. 



+ Register Post as http request

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/embedding/process' \
--header 'Content-Type: application/json' \
--data-raw '{}'
```

```bash
[
    {
        "content": "\"What is AWEL?\": Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application\ndevelopment. It provides great functionality and flexibility. Through the AWEL API, you can focus on the development of business logic for LLMs applications\nwithout paying attention to cumbersome model and environment details.  \nAWEL adopts a layered API design. AWEL's layered API design architecture is shown in the figure below.  \n<p align=\"left\">\n<img src={'/img/awel.png'} width=\"480px\"/>\n</p>",
        "metadata": {
            "Header1": "What is AWEL?",
            "source": "../../docs/docs/awel/awel.md"
        },
        "chunk_id": "c1ffa671-76d0-4c7a-b2dd-0b08dfd37712",
        "chunk_name": "",
        "score": 0.0,
        "summary": "",
        "separator": "\n",
        "retriever": null
    },...
  ]
```



