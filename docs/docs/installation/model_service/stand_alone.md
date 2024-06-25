# Stand-alone Deployment

## Preparation
```bash
# download source code
git clone https://github.com/eosphoros-ai/DB-GPT.git

cd DB-GPT
```

## Environment installation

```bash
# create a virtual environment
conda create -n dbgpt_env python=3.10

# activate virtual environment
conda activate dbgpt_env
```

## Install dependencies

```bash
pip install -e ".[default]"
```

## Model download

Download LLM and Embedding model

:::info note

⚠️ If there are no GPU resources, it is recommended to use the proxy model, such as OpenAI, Qwen, ERNIE Bot, etc.
:::


```bash
mkdir models && cd models

# download embedding model, eg: text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

:::tip

Set up proxy API and modify `.env`configuration
:::

```bash
#set LLM_MODEL TYPE
LLM_MODEL=proxyllm
#set your Proxy Api key and Proxy Server url
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
```

:::info note
⚠️ If you have GPU resources, you can use local models to deploy
:::

```bash
mkdir models && cd models

# # download embedding model, eg: glm-4-9b-chat or  
git clone https://huggingface.co/THUDM/glm-4-9b-chat

# download embedding model, eg: text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese

popd

```

## Command line startup

```bash
LLM_MODEL=glm-4-9b-chat 
dbgpt start webserver --port 6006
```
By default, the `dbgpt start webserver command` will start the `webserver`, `model controller`, and `model worker` through a single Python process. In the above command, port `6006` is specified.



## View and verify model serving

:::tip
view and display all model services
:::
```bash
dbgpt model list 
```

```bash
# result
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|    Model Name   | Model Type |    Host    | Port | Healthy | Enabled | Prompt Template |       Last Heartbeat       |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
| glm-4-9b-chat |    llm     | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.201313 |
|  WorkerManager  |  service   | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.246756 |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+

```
Where `WorkerManager` is the management process of `Model Workers`

:::tip
check and verify model serving
:::
```bash
dbgpt model chat --model_name glm-4-9b-chat
```

The above command will launch an interactive page that allows you to talk to the model through the terminal.

```bash
Chatbot started with model glm-4-9b-chat. Type 'exit' to leave the chat.


You: Hello
Bot: Hello! How can I assist you today?

You: 
```

