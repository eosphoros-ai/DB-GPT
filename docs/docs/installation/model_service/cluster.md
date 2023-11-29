# Cluster Deployment

## Install command line tools
All the following operations are completed through the `dbgpt` command. To use the `dbgpt` command, you first need to install the `DB-GPT` project. You can install it through the following command

```python
$ pip install -e ".[default]"
```
It can also be used in script mode
```python
$ python pilot/scripts/cli_scripts.py
```

## Start Model Controller
```python
$ dbgpt start controller
```

## View log
```python
$ docker logs db-gpt-webserver-1 -f
```
By default, `Model Server` will start on port `8000`

## Start Model Worker

:::tip
Start `chatglm2-6b` model Worker
:::

```python
dbgpt start worker --model_name chatglm2-6b \
--model_path /app/models/chatglm2-6b \
--port 8001 \
--controller_addr http://127.0.0.1:8000
```


:::tip
Start `vicuna-13b-v1.5` model Worker
:::

```python
dbgpt start worker --model_name vicuna-13b-v1.5 \
--model_path /app/models/vicuna-13b-v1.5 \
--port 8002 \
--controller_addr http://127.0.0.1:8000
```
:::info note
⚠️  Make sure to use your own model name and model path.

:::


## Start the embedding model service

```python
dbgpt start worker --model_name text2vec \
--model_path /app/models/text2vec-large-chinese \
--worker_type text2vec \
--port 8003 \
--controller_addr http://127.0.0.1:8000
```
:::info note
⚠️  Make sure to use your own model name and model path.

:::

:::tip
View and inspect deployed models
:::


```python
$ dbgpt model list

+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|    Model Name   | Model Type |    Host    | Port | Healthy | Enabled | Prompt Template |       Last Heartbeat       |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
|   chatglm2-6b   |    llm     | 172.17.0.2 | 8001 |   True  |   True  |                 | 2023-09-12T23:04:31.287654 |
|  WorkerManager  |  service   | 172.17.0.2 | 8001 |   True  |   True  |                 | 2023-09-12T23:04:31.286668 |
|  WorkerManager  |  service   | 172.17.0.2 | 8003 |   True  |   True  |                 | 2023-09-12T23:04:29.845617 |
|  WorkerManager  |  service   | 172.17.0.2 | 8002 |   True  |   True  |                 | 2023-09-12T23:04:24.598439 |
|     text2vec    |  text2vec  | 172.17.0.2 | 8003 |   True  |   True  |                 | 2023-09-12T23:04:29.844796 |
| vicuna-13b-v1.5 |    llm     | 172.17.0.2 | 8002 |   True  |   True  |                 | 2023-09-12T23:04:24.597775 |
+-----------------+------------+------------+------+---------+---------+-----------------+----------------------------+
```


## Use model serving

The model service deployed as above can be used through dbgpt_server. First modify the `.env` configuration file to change the connection model address

```python
dbgpt start webserver --light
```

## Start Webserver 

```python
LLM_MODEL=vicuna-13b-v1.5
# The current default MODEL_SERVER address is the address of the Model Controller
MODEL_SERVER=http://127.0.0.1:8000
```
`--light` means not to start the embedded model service.


Or it can be started directly by command to formulate the model.
```python
LLM_MODEL=chatglm2-6b dbgpt start webserver --light
```

## Command line usage
For more information about the use of the command line, you can view the command line help. The following is a reference example.


:::tip
View dbgpt help `dbgpt --help`
:::

```python
dbgpt --help

Already connect 'dbgpt'
Usage: dbgpt [OPTIONS] COMMAND [ARGS]...

Options:
  --log-level TEXT  Log level
  --version         Show the version and exit.
  --help            Show this message and exit.

Commands:
  install    Install dependencies, plugins, etc.
  knowledge  Knowledge command line tool
  model      Clients that manage model serving
  start      Start specific server.
  stop       Start specific server.
  trace      Analyze and visualize trace spans.
```


:::tip
Check the dbgpt start command `dbgpt start --help`
:::

```python
dbgpt start --help

Already connect 'dbgpt'
Usage: dbgpt start [OPTIONS] COMMAND [ARGS]...

  Start specific server.

Options:
  --help  Show this message and exit.

Commands:
  apiserver   Start apiserver
  controller  Start model controller
  webserver   Start webserver(dbgpt_server.py)
  worker      Start model worker
(dbgpt_env) magic@B-4TMH9N3X-2120 ~ %
```

:::tip
View the dbgpt start model service help command `dbgpt start worker --help`
:::

```python
dbgpt start worker --help

Already connect 'dbgpt'
Usage: dbgpt start worker [OPTIONS]

  Start model worker

Options:
  --model_name TEXT               Model name  [required]
  --model_path TEXT               Model path  [required]
  --worker_type TEXT              Worker type
  --worker_class TEXT             Model worker class,
                                  pilot.model.cluster.DefaultModelWorker
  --model_type TEXT               Model type: huggingface, llama.cpp, proxy
                                  and vllm  [default: huggingface]
  --host TEXT                     Model worker deploy host  [default: 0.0.0.0]
  --port INTEGER                  Model worker deploy port  [default: 8001]
  --daemon                        Run Model Worker in background
  --limit_model_concurrency INTEGER
                                  Model concurrency limit  [default: 5]
  --standalone                    Standalone mode. If True, embedded Run
                                  ModelController
  --register                      Register current worker to model controller
                                  [default: True]
  --worker_register_host TEXT     The ip address of current worker to register
                                  to ModelController. If None, the address is
                                  automatically determined
  --controller_addr TEXT          The Model controller address to register
  --send_heartbeat                Send heartbeat to model controller
                                  [default: True]
  --heartbeat_interval INTEGER    The interval for sending heartbeats
                                  (seconds)  [default: 20]
  --log_level TEXT                Logging level
  --log_file TEXT                 The filename to store log  [default:
                                  dbgpt_model_worker_manager.log]
  --tracer_file TEXT              The filename to store tracer span records
                                  [default:
                                  dbgpt_model_worker_manager_tracer.jsonl]
  --tracer_storage_cls TEXT       The storage class to storage tracer span
                                  records
  --device TEXT                   Device to run model. If None, the device is
                                  automatically determined
  --prompt_template TEXT          Prompt template. If None, the prompt
                                  template is automatically determined from
                                  model path, supported template: zero_shot,vi
                                  cuna_v1.1,llama-2,codellama,alpaca,baichuan-
                                  chat,internlm-chat
  --max_context_size INTEGER      Maximum context size  [default: 4096]
  --num_gpus INTEGER              The number of gpus you expect to use, if it
                                  is empty, use all of them as much as
                                  possible
  --max_gpu_memory TEXT           The maximum memory limit of each GPU, only
                                  valid in multi-GPU configuration
  --cpu_offloading                CPU offloading
  --load_8bit                     8-bit quantization
  --load_4bit                     4-bit quantization
  --quant_type TEXT               Quantization datatypes, `fp4` (four bit
                                  float) and `nf4` (normal four bit float),
                                  only valid when load_4bit=True  [default:
                                  nf4]
  --use_double_quant              Nested quantization, only valid when
                                  load_4bit=True  [default: True]
  --compute_dtype TEXT            Model compute type
  --trust_remote_code             Trust remote code  [default: True]
  --verbose                       Show verbose output.
  --help                          Show this message and exit.
```

:::tip
View dbgpt model service related commands `dbgpt model --help`
:::

```python
dbgpt model --help


Already connect 'dbgpt'
Usage: dbgpt model [OPTIONS] COMMAND [ARGS]...

  Clients that manage model serving

Options:
  --address TEXT  Address of the Model Controller to connect to. Just support
                  light deploy model, If the environment variable
                  CONTROLLER_ADDRESS is configured, read from the environment
                  variable
  --help          Show this message and exit.

Commands:
  chat     Interact with your bot from the command line
  list     List model instances
  restart  Restart model instances
  start    Start model instances
  stop     Stop model instances
```



