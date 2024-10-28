# dbgpts

[dbgpts](https://github.com/eosphoros-ai/dbgpts) contains some data apps, AWEL operators, AWEL workflows, agents and resources 
which build upon the DB-GPT.

## Introduction

### Why We Need `dbgpts`

In a production-level LLM's application, there are many components that need to be
integrated, and you want to start your research and creativity quickly by using the 
existing components.

At the same time, we hope that the core components of DB-GPT keep simple and easy to
maintain, and some complex components can be developed in the form of plugins.

So, we need a plugin system to extend the capabilities of DB-GPT, and `dbgpts` is the
plugin system or a part of ecosystem of DB-GPT.

### What Is `dbgpts`

There are some concepts in `dbgpts`:
- `app`: It includes data apps, AWEL operators, AWEL workflows, agents and resources, sometimes, we
call it `dbgpts` app or `dbgpts` package.
- `repo`: It is a repository of `dbgpts` apps, you can install a `dbgpts` app from a `dbgpts` repo,
the default `dbgpts` repo is [eosphoros-ai/dbgpts](https://github.com/eosphoros-ai/dbgpts), you can
also create your own `dbgpts` repo or use other's `dbgpts` repo.

### How To Run `dbgpts`

1. When you install a `dbgpts` app, it will be loaded to your DB-GPT webserver automatically,
and you can use it in the DB-GPT webserver or trigger it by command line `dbgpt run ...`.
2. You can also run a `dbgpts` app as a command line tool, you can use it in your terminal by
`dbgpt app run ...` with `--local` option, it will run the app in your local environment.

## Quick Start

Let's install a `dbgpts` package named [awel-flow-simple-streaming-chat](https://github.com/eosphoros-ai/dbgpts/tree/main/workflow/awel-flow-simple-streaming-chat)

```bash
dbgpt app install awel-flow-simple-streaming-chat -U
```

### Run The App Locally

Then, you can run the app in your terminal:

```bash
dbgpt run flow --local chat \
--name awel-flow-simple-streaming-chat \
--model "gpt-3.5-turbo" \
--messages "hello" \
--stream
```
- `dbgpt run flow`: Means you want to run a AWEL workflow.
- `--local`: Means you want to run the workflow in your local environment without 
starting the DB-GPT webserver, it will find the `app` installed in your local 
environment, then run it, also, you can use `--file` to specify the python file.
- `--name`: The name of the app.
- `--model`: The LLM model you want to use,  `awel-flow-simple-streaming-chat` will 
use OpenAI LLM by default if you run it with `--local`.
- `--messages`: The messages you want to send to the LLM.
- `--stream`: Means you want to run the workflow in streaming mode.

The output will be like this:

```bash
You: hello
[~info] Chat stream started
[~info] JSON data: {"model": "gpt-3.5-turbo", "messages": "hello", "stream": true}
Bot: 
Hello! How can I assist you today?
🎉 Chat stream finished, timecost: 1.12 s
```

### Run The App In DB-GPT Webserver

After you install the `awel-flow-simple-streaming-chat` app, you can run it in the DB-GPT webserver.
Also, you can use the `dbgpt` command line tool to trigger the app.

```bash
dbgpt run flow chat \
--name awel-flow-simple-streaming-chat \
--model "chatgpt_proxyllm" \
--messages "hello" \
--stream
```

You just remove the `--local` option, then the command will connect to the DB-GPT webserver and run the app.
And you should modify the `--model` option to your model name in the DB-GPT webserver.

The output will be like this:

```bash
You: hello
[~info] Chat stream started
[~info] JSON data: {"model": "chatgpt_proxyllm", "messages": "hello", "stream": true, "chat_param": "1ecd35d4-a60a-420b-8943-8fc44f7f054a", "chat_mode": "chat_flow"}
Bot: 
Hello! How can I assist you today?
🎉 Chat stream finished, timecost: 0.98 s
```

## Run The App With `command` Mode

In previous examples, we run the app in `chat` mode, but not all `dbgpts` apps support `chat` mode,
some apps support `command` mode, you can run the app with `dbgpt run flow cmd` command.

### Run The App Locally

```bash
dbgpt run flow --local cmd \
--name awel-flow-simple-streaming-chat \
-d '
{
    "model": "gpt-3.5-turbo",
    "messages": "hello",
    "stream": true
}
'
```

We replace the `chat` mode with `cmd` mode, and use `-d` option to specify the data in JSON format.

The output will be like this:

```bash
[~info] Flow started
[~info] JSON data: {"model": "gpt-3.5-turbo", "messages": "hello", "stream": true}
Command output: 
Hello! How can I assist you today?
🎉 Flow finished, timecost: 1.35 s
```

### Run The App In DB-GPT Webserver

Just remove the `--local` option, then the command will connect to the DB-GPT webserver and run the app.

```bash
dbgpt run flow cmd \
--name awel-flow-simple-streaming-chat \
-d '
{
    "model": "chatgpt_proxyllm",
    "messages": "hello",
    "stream": true
}
'
```

The output will be like this:

```bash
[~info] Flow started
[~info] JSON data: {"model": "chatgpt_proxyllm", "messages": "hello", "stream": true}
Command output: 
Hello! How can I assist you today?
🎉 Flow finished, timecost: 1.09 s
```

## `chat` Mode vs `command` Mode

In short, `chat` mode is used for chat applications, and `command` mode is used to 
trigger the app with a command.

For example, you want to load your documents to the DB-GPT, you can use `command` mode
to trigger the app to load the documents, it always runs once and the result will be
returned.

And `chat` mode is a special case of `command` mode, it provides a chat interface to
the user, and you can chat with the LLM in an interactive way.


## Run You App With Python Script

If you run app locally, it will find the app which is installed in your local environment,
also, you can run the app by providing the python file.

Let's create a python file named `simple_chat_app.py`:

```python
import os
from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import ModelMessage, ModelRequest
from dbgpt.core.awel import DAG, HttpTrigger, MapOperator
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.model.operators import LLMOperator


class TriggerReqBody(BaseModel):
    model: str = Field(..., description="Model name")
    messages: str = Field(..., description="User input")


class RequestHandleOperator(MapOperator[TriggerReqBody, ModelRequest]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, input_value: TriggerReqBody) -> ModelRequest:
        messages = [ModelMessage.build_human_message(input_value.messages)]
        return ModelRequest.build_request(input_value.model, messages)


with DAG("dbgpts_simple_chat_app") as dag:
    # Receive http request and trigger dag to run.
    trigger = HttpTrigger(
        "/dbgpts/simple_chat_app", methods="POST", request_body=TriggerReqBody
    )
    llm_client = OpenAILLMClient(
        model_alias="gpt-3.5-turbo",  # or other models, eg. "gpt-4o"
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    request_handle_task = RequestHandleOperator()
    llm_task = LLMOperator(llm_client=llm_client)
    model_parse_task = MapOperator(lambda out: out.text)
    trigger >> request_handle_task >> llm_task >> model_parse_task
```

Then you can run the app by providing the python file:

```bash
dbgpt run flow --local --file simple_chat_app.py \
chat \
--name dbgpts_simple_chat_app \
--model "gpt-3.5-turbo" \
--messages "hello"
```

The output will be like this:

```bash
You: hello
[~info] Chat started
[~info] JSON data: {"model": "gpt-3.5-turbo", "messages": "hello", "stream": false}
Bot: 
Hello! How can I assist you today?                                                                                                                                                       

🎉 Chat stream finished, timecost: 1.06 s
```

And you can run previous examples with `command` mode.

```bash
dbgpt run flow --local --file simple_chat_app.py \
cmd \
--name dbgpts_simple_chat_app \
-d '
{
    "model": "gpt-3.5-turbo",
    "messages": "hello"
}'
```

The output will be like this:

```bash
[~info] Flow started
[~info] JSON data: {"model": "gpt-3.5-turbo", "messages": "hello"}
Command output: 
Hello! How can I assist you today?
🎉 Flow finished, timecost: 1.04 s
```

## Show Your App In DB-GPT Webserver

When you install the workflow, you can see the workflow in the DB-GPT webserver, you can open
the **AWEL Flow** page, then you can see the workflow named `awel_flow_simple_streaming_chat`.

<p align="left">
  <img src={'/img/dbgpts/awel_flow_simple_streaming_chat_1.png'} width="720px" />
</p>

Then you can click the `edit` button to see the details of the workflow.
<p align="left">
  <img src={'/img/dbgpts/awel_flow_simple_streaming_chat_2.png'} width="720px" />
</p>

Note: Not all workflows support editing, there are two types of workflows according to the
definition type: `json` and `python`, the `json` type workflow can be edited in the DB-GPT,
We will show you more details in the next sections.
