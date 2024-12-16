# Knowledge Graph Process Workflow

# Introduction
Unlike traditional Native RAG, which requires vectors as data carriers, GraphRAG requires triple extraction (entity -> relationship -> entity) to build a knowledge graph, so the entire knowledge processing can also be regarded as the process of building a knowledge graph. 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734357331126-a3a96fd7-c8fb-4208-8e3b-be798d1b73b4.png)

# Applicable Scenarios 
+ It is necessary to use GraphRAG ability to mine the relationship between knowledge for multi-step reasoning. 
+ Make up for the lack of integrity of Naive RAG in the recall context. 

# How to use 
+ Enter the AWEL interface and add a workflow 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734354927468-feed0ac7-e0fe-45e8-b85c-aba170084f82.png)

+ Import Knowledge Processing Template 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734356276305-a6e03aff-ba89-40c4-be2d-f88dff29d0f5.png)

+ Adjust parameters and save 

![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1734356745373-4e449611-d0bc-4735-b142-0aebafaa34d6.png)

    - `document knowledge loading operator `: Knowledge loading factory, by loading the specified document type, find the corresponding document processor for document content parsing. 
    - `Document Chunk slicing operator `: Slice the loaded document content according to the specified slicing parameters. 
    - `Knowledge Graph processing operator `: You can connect different knowledge graph processing operators, including native knowledge graph processing operators and community summary Knowledge Graph processing operators. You can also specify different graph databases for storage. Currently, TuGraph databases are supported. 



+ Register Post as http request

```bash
curl --location --request POST 'http://localhost:5670/api/v1/awel/trigger/rag/knowledge/kg/process' \
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



