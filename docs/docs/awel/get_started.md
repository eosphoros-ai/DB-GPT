# Get Started

AWEL(Agentic Workflow Expression Language) makes it easy to build complex llm apps, and it provides great functionality and flexibility. 

## Basic example use AWEL: http request + output rewrite

The basic usage about AWEL is to build a http request and rewrite some output value. To see how this works, let's see an example.

### DAG Planning
First, let's look at an introductory example of basic AWEL orchestration. The core function of the example is the handling of input and output for an HTTP request. Thus, the entire orchestration consists of only two steps:
- HTTP Request
- Processing HTTP Response Result

In DB-GPT, some basic dependent operators have already been encapsulated and can be referenced directly.

```python
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
```

### Custom Operator

Define an HTTP request body that accepts two parameters: name and age.

```python
class TriggerReqBody(BaseModel):
    name: str = Field(..., description="User name")
    age: int = Field(18, description="User age")
```

Define a Request handler operator called `RequestHandleOperator`, which is an operator that extends the basic `MapOperator`. The actions of the `RequestHandleOperator` are straightforward: parse the request body and extract the name and age fields, then concatenate them into a sentence. For example:

> "Hello, zhangsan, your age is 18."

```python
class RequestHandleOperator(MapOperator[TriggerReqBody, str]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> str:
        print(f"Receive input value: {input_value}")
        return f"Hello, {input_value.name}, your age is {input_value.age}"
```

### DAG Pipeline

After writing the above operators, they can be assembled into a DAG orchestration. This DAG has a total of two nodes: the first node is an `HttpTrigger`, which primarily processes HTTP requests (this operator is built into DB-GPT), and the second node is the newly defined `RequestHandleOperator` that processes the request body. The DAG code below can be used to link the two nodes together.

```python
with DAG("simple_dag_example") as dag:
    trigger = HttpTrigger("/examples/hello", request_body=TriggerReqBody)
    map_node = RequestHandleOperator()
    trigger >> map_node
```

### Access Verification

Before performing access verification, the project needs to be started first: `python dbgpt/app/dbgpt_server.py`

```bash
% curl -X GET http://127.0.0.1:5000/api/v1/awel/trigger/examples/hello\?name\=zhangsan
"Hello, zhangsan, your age is 18"
```

Of course, to make it more convenient for users to test, we also provide a test environment. This test environment allows testing without starting the dbgpt_server. Add the following code below simple_dag_example, then directly run the simple_dag_example.py script to run the test script without starting the project.

```python
if __name__ == "__main__":
    if dag.leaf_nodes[0].dev_mode:
        # Development mode, you can run the dag locally for debugging.
        from dbgpt.core.awel import setup_dev_environment
        setup_dev_environment([dag], port=5555)
    else:
        # Production mode, DB-GPT will automatically load and execute the current file after startup.
        pass
```

```bash
curl -X GET http://127.0.0.1:5555/api/v1/awel/trigger/examples/hello\?name\=zhangsan
"Hello, zhangsan, your age is 18"
```

[simple_dag_example](/examples/awel/simple_dag_example.py)