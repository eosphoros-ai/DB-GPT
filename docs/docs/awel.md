# AWEL(Agentic Workflow Expression Language)

Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application
development. It provides great functionality and flexibility. Through the AWEL API, you can focus on the development of business logic for LLMs applications
without paying attention to cumbersome model and environment details.

AWEL adopts a layered API design. AWEL's layered API design architecture is shown in the figure below.


<p align="left">
  <img src={'/img/awel.png'} width="480px"/>
</p>

## AWEL Design

AWEL is divided into three levels in deign, namely the operator layer, AgentFream layer and DSL layer. The following is a brief introduction
to the three levels.

- **Operator layer**
The operator layer refers to the most basic operation atoms in the LLM application development process, 
such as when developing a RAG application. Retrieval, vectorization, model interaction, prompt processing, etc. 
are all basic operators. In the subsequent development, the framework will further abstract and standardize the design of operators. 
A set of operators can be quickly implemented based on standard APIs

- **AgentFream layer**
The AgentFream layer further encapsulates operators and can perform chain calculations based on operators. 
This layer of chain computing also supports distribution, supporting a set of chain computing operations such as filter, join, map, reduce, etc. More calculation logic will be supported in the future.

- **DSL layer**
The DSL layer provides a set of standard structured representation languages, which can complete the operations of AgentFream and operators by writing DSL statements, making it more deterministic to write large model applications around data, avoiding the uncertainty of writing in natural language, and making it easier to write around data. Application programming with large models becomes deterministic application programming.

## Examples
The preliminary version of AWEL has alse been released, and we have provided some built-in usage examples.

## Operators

### Example of API-RAG 
You can find [source code](https://github.com/eosphoros-ai/DB-GPT/blob/main/examples/awel/simple_rag_example.py) from `examples/awel/simple_rag_example.py`
```python
with DAG("simple_rag_example") as dag:
    trigger_task = HttpTrigger(
        "/examples/simple_rag", methods="POST", request_body=ConversationVo
    )
    req_parse_task = RequestParseOperator()
    # TODO should register prompt template first
    prompt_task = PromptManagerOperator()
    history_storage_task = ChatHistoryStorageOperator()
    history_task = ChatHistoryOperator()
    embedding_task = EmbeddingEngingOperator()
    chat_task = BaseChatOperator()
    model_task = ModelOperator()
    output_parser_task = MapOperator(lambda out: out.to_dict()["text"])

    (
        trigger_task
        >> req_parse_task
        >> prompt_task
        >> history_storage_task
        >> history_task
        >> embedding_task
        >> chat_task
        >> model_task
        >> output_parser_task
    )

```
Bit operations will arrange the entire process in the form of DAG

<p align="left">
  <img src={'/img/awel_dag_flow.png'} width="360px" />
</p>

#### Example of LLM + cache

<p align="left">
  <img src={'/img/awel_cache_flow.png'} width="360px" />
</p>


###  AgentFream Example
```python
af = AgentFream(HttpSource("/examples/run_code", method = "post"))
result = (
    af
    .text2vec(model="text2vec")
    .filter(vstore, store = "chromadb", db="default")
    .llm(model="vicuna-13b", temperature=0.7)
    .map(code_parse_func)
    .map(run_sql_func)
    .reduce(lambda a, b: a + b)
)
result.write_to_sink(type='source_slink')
```

### DSL Example

``` python
CREATE WORKFLOW RAG AS
BEGIN
    DATA requestData = RECEIVE REQUEST FROM 
    		http_source("/examples/rags", method = "post");
        
    DATA processedData = TRANSFORM requestData USING embedding(model = "text2vec");
    DATA retrievedData = RETRIEVE DATA 
    		FROM vstore(database = "chromadb", key = processedData)
    		ON ERROR FAIL;
        
    DATA modelResult = APPLY LLM "vicuna-13b" 
    		WITH DATA retrievedData AND PARAMETERS (temperature = 0.7)
    		ON ERROR RETRY 2 TIMES;
        
    RESPOND TO http_source WITH modelResult
    		ON ERROR LOG "Failed to respond to request";
END;
```

## Currently supported operators
- **Basic Operators**
    - BaseOperator
    - JoinOperator
    - ReduceOperator
    - MapOperator
    - BranchOperator
    - InputOperator
    - TriggerOperator
- ** Stream Operators**
    - StreamifyAbsOperator
    - UnstreamifyAbsOperator
    - TransformStreamAbsOperator

## Executable environment
- Stand-alone environment
- Ray environment


