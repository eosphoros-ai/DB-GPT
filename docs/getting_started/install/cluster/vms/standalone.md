Standalone Deployment
==================================
(standalone-index)=

### Install Prepare
```commandline
git clone https://github.com/eosphoros-ai/DB-GPT.git

cd DB-GPT
```

### Create conda environment
```commandline
conda create -n dbgpt_env python=3.10

conda activate dbgpt_env
```


### Install Default Requirements
```commandline
# Install Default Requirements
pip install -e ".[default]"
```

### Download and Prepare LLM Model and Embedding Model
```{tip}
 If you don't have high performance hardware server
```
you can use openai api, tongyi api , bard api, etc.
```commandline
mkdir models && cd models

# download embedding model, eg: text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese

```

set proxy api in .env
```commandline
#set LLM_MODEL TYPE
LLM_MODEL=proxyllm
#set your Proxy Api key and Proxy Server url
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
```
```{tip}
If you have high performance hardware server
```

```commandline
mkdir models && cd models

# # download embedding model, eg: vicuna-13b-v1.5 or  
git clone https://huggingface.co/lmsys/vicuna-13b-v1.5

# download embedding model, eg: text2vec-large-chinese
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese

popd
```
### Start all services with a single command.
```commandline
LLM_MODEL=vicuna-13b-v1.5 
dbgpt start webserver --port 6006
```
By default, the "dbgpt start webserver" command will start the Webserver, Model Controller, and Model Worker in a single Python process. Here, we specify the service to be started on port 6006.

### View and validate the model service in the command line, you can use the following commands
##### 1.list the started model services and deployed Model Workers, you can use the following command
```commandline
dbgpt model list
```
output is:
```commandline
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|    Model Name   | Model Type |    Host    | Port | Healthy | Enabled | Prompt Template |       Last Heartbeat       |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
| vicuna-13b-v1.5 |    llm     | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.201313 |
|  WorkerManager  |  service   | 172.17.0.9 | 6006 |   True  |   True  |                 | 2023-10-16T19:49:59.246756 |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
```
The WorkerManager is the management process for Model Workers

##### validate the deployed model in the command line, you can use the following command
```commandline
dbgpt model chat --model_name vicuna-13b-v1.5
```
Then an interactive page will be launched where you can have a conversation with the deployed LLM in the terminal.
```commandline
Chatbot started with model vicuna-13b-v1.5. Type 'exit' to leave the chat.


You: Hello
Bot: Hello! How can I assist you today?

You: 
```