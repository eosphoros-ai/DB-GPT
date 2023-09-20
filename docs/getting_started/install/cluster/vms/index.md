Local cluster deployment
==================================
(local-cluster-index)=
## Model cluster deployment


**Installing Command-Line Tool**

All operations below are performed using the `dbgpt` command. To use the `dbgpt` command, you need to install the DB-GPT project with `pip install -e ".[default]"`. Alternatively, you can use `python pilot/scripts/cli_scripts.py` as a substitute for the `dbgpt` command.

### Launch Model Controller

```bash
dbgpt start controller
```

By default, the Model Controller starts on port 8000.


### Launch LLM Model Worker

If you are starting `chatglm2-6b`:

```bash
dbgpt start worker --model_name chatglm2-6b \
--model_path /app/models/chatglm2-6b \
--port 8001 \
--controller_addr http://127.0.0.1:8000
```

If you are starting `vicuna-13b-v1.5`:

```bash
dbgpt start worker --model_name vicuna-13b-v1.5 \
--model_path /app/models/vicuna-13b-v1.5 \
--port 8002 \
--controller_addr http://127.0.0.1:8000
```

Note: Be sure to use your own model name and model path.

### Launch Embedding Model Worker

```bash

dbgpt start worker --model_name text2vec \
--model_path /app/models/text2vec-large-chinese \
--worker_type text2vec \
--port 8003 \
--controller_addr http://127.0.0.1:8000
```

Note: Be sure to use your own model name and model path.

Check your model:

```bash
dbgpt model list
```

You will see the following output:
```
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

### Connect to the model service in the webserver (dbgpt_server)

**First, modify the `.env` file to change the model name and the Model Controller connection address.**

```bash
LLM_MODEL=vicuna-13b-v1.5
# The current default MODEL_SERVER address is the address of the Model Controller
MODEL_SERVER=http://127.0.0.1:8000
```

#### Start the webserver

```bash
dbgpt start webserver --light
```

`--light`  indicates not to start the embedded model service.

Alternatively, you can prepend the command with `LLM_MODEL=chatglm2-6b` to start:

```bash
LLM_MODEL=chatglm2-6b dbgpt start webserver --light
```


### More Command-Line Usages

You can view more command-line usages through the help command.

**View the `dbgpt` help**
```bash
dbgpt --help
```

You will see the basic command parameters and usage:

```
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
```

**View the `dbgpt start` help**

```bash
dbgpt start --help
```

Here you can see the related commands and usage for start:

```
Usage: dbgpt start [OPTIONS] COMMAND [ARGS]...

  Start specific server.

Options:
  --help  Show this message and exit.

Commands:
  apiserver   Start apiserver(TODO)
  controller  Start model controller
  webserver   Start webserver(dbgpt_server.py)
  worker      Start model worker
```

**View the `dbgpt start worker`help**

```bash
dbgpt start worker --help
```

Here you can see the parameters to start Model Worker:

```
Usage: dbgpt start worker [OPTIONS]

  Start model worker

Options:
  --model_name TEXT               Model name  [required]
  --model_path TEXT               Model path  [required]
  --worker_type TEXT              Worker type
  --worker_class TEXT             Model worker class,
                                  pilot.model.cluster.DefaultModelWorker
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
  --device TEXT                   Device to run model. If None, the device is
                                  automatically determined
  --model_type TEXT               Model type, huggingface, llama.cpp and proxy
                                  [default: huggingface]
  --prompt_template TEXT          Prompt template. If None, the prompt
                                  template is automatically determined from
                                  model path, supported template: zero_shot,vi
                                  cuna_v1.1,llama-2,alpaca,baichuan-chat
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

**View the `dbgpt model`help**

```bash
dbgpt model --help
```

The `dbgpt model ` command can connect to the Model Controller via the Model Controller address and then manage a remote model:

```
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