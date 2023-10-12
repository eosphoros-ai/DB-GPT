# Debugging
-------------

DB-GPT provides a set of tools to help you troubleshoot and resolve some of the issues you may encounter.


## Trace Logs

DB-GPT writes some critical system runtime information to trace logs. By default, these are located in `logs/dbgpt*.jsonl`.

DB-GPT also offers a command-line tool, `dbgpt trace`, to help you analyze these trace logs. You can see its specific usage with the command `dbgpt trace --help`.


## Viewing Chat Details

You can use the `dbgpt trace chat` command to view chat details. By default, it will display the latest chat message.

### Viewing Service Runtime Information

```bash
dbgpt trace chat --hide_conv
```

You will see an output like:

```
+------------------------+--------------------------+-----------------------------+------------------------------------+
| Config Key (Webserver) | Config Value (Webserver) | Config Key (EmbeddingModel) |   Config Value (EmbeddingModel)    |
+------------------------+--------------------------+-----------------------------+------------------------------------+
|          host          |         0.0.0.0          |          model_name         |              text2vec              |
|          port          |           5000           |          model_path         | /app/models/text2vec-large-chinese |
|         daemon         |          False           |            device           |                cuda                |
|         share          |          False           |     normalize_embeddings    |                None                |
|    remote_embedding    |          False           |                             |                                    |
|       log_level        |           None           |                             |                                    |
|         light          |          False           |                             |                                    |
+------------------------+--------------------------+-----------------------------+------------------------------------+
+--------------------------+-----------------------------+----------------------------+------------------------------+
| Config Key (ModelWorker) |  Config Value (ModelWorker) | Config Key (WorkerManager) | Config Value (WorkerManager) |
+--------------------------+-----------------------------+----------------------------+------------------------------+
|        model_name        |       vicuna-13b-v1.5       |         model_name         |       vicuna-13b-v1.5        |
|        model_path        | /app/models/vicuna-13b-v1.5 |         model_path         | /app/models/vicuna-13b-v1.5  |
|          device          |             cuda            |        worker_type         |             None             |
|        model_type        |         huggingface         |        worker_class        |             None             |
|     prompt_template      |             None            |         model_type         |         huggingface          |
|     max_context_size     |             4096            |            host            |           0.0.0.0            |
|         num_gpus         |             None            |            port            |             5000             |
|      max_gpu_memory      |             None            |           daemon           |            False             |
|      cpu_offloading      |            False            |  limit_model_concurrency   |              5               |
|        load_8bit         |            False            |         standalone         |             True             |
|        load_4bit         |            False            |          register          |             True             |
|        quant_type        |             nf4             |    worker_register_host    |             None             |
|     use_double_quant     |             True            |      controller_addr       |    http://127.0.0.1:5000     |
|      compute_dtype       |             None            |       send_heartbeat       |             True             |
|    trust_remote_code     |             True            |     heartbeat_interval     |              20              |
|         verbose          |            False            |         log_level          |             None             |
+--------------------------+-----------------------------+----------------------------+------------------------------+
```

### Viewing the Latest Chat Message

```bash
dbgpt trace chat --hide_run_params
```

You will see an output like:

```
+-------------------------------------------------------------------------------------------------------------------------------------------+
|                                                             Chat Trace Details                                                            |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|      Key       |                                                       Value Value                                                        |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|    trace_id    |                                           5d1900c3-5aad-4159-9946-fbb600666530                                           |
|    span_id     |                        5d1900c3-5aad-4159-9946-fbb600666530:14772034-bed4-4b4e-b43f-fcf3a8aad6a7                         |
|    conv_uid    |                                           5e456272-68ac-11ee-9fba-0242ac150003                                           |
|   user_input   |                                                       Who are you?                                                       |
|   chat_mode    |                                                       chat_normal                                                        |
|  select_param  |                                                           None                                                           |
|   model_name   |                                                     vicuna-13b-v1.5                                                      |
|  temperature   |                                                           0.6                                                            |
| max_new_tokens |                                                           1024                                                           |
|      echo      |                                                          False                                                           |
|  llm_adapter   |                        FastChatLLMModelAdaperWrapper(fastchat.model.model_adapter.VicunaAdapter)                         |
|  User prompt   | A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polit |
|                |                             e answers to the user's questions. USER: Who are you? ASSISTANT:                             |
|  Model output  |  You can call me Vicuna, and I was trained by Large Model Systems Organization (LMSYS) researchers as a language model.  |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
```


### Viewing Chat Details and Call Chain

```bash
dbgpt trace chat --hide_run_params --tree
```

You will see an output like:

```

Invoke Trace Tree:

Operation: DB-GPT-Web-Entry (Start: 2023-10-12 03:06:43.180, End: None)
  Operation: get_chat_instance (Start: 2023-10-12 03:06:43.258, End: None)
  Operation: get_chat_instance (Start: 2023-10-12 03:06:43.258, End: 2023-10-12 03:06:43.424)
  Operation: stream_generator (Start: 2023-10-12 03:06:43.425, End: None)
    Operation: BaseChat.stream_call (Start: 2023-10-12 03:06:43.426, End: None)
      Operation: WorkerManager.generate_stream (Start: 2023-10-12 03:06:43.426, End: None)
        Operation: DefaultModelWorker.generate_stream (Start: 2023-10-12 03:06:43.428, End: None)
          Operation: DefaultModelWorker_call.generate_stream_func (Start: 2023-10-12 03:06:43.430, End: None)
          Operation: DefaultModelWorker_call.generate_stream_func (Start: 2023-10-12 03:06:43.430, End: 2023-10-12 03:06:48.518)
        Operation: DefaultModelWorker.generate_stream (Start: 2023-10-12 03:06:43.428, End: 2023-10-12 03:06:48.518)
      Operation: WorkerManager.generate_stream (Start: 2023-10-12 03:06:43.426, End: 2023-10-12 03:06:48.518)
    Operation: BaseChat.stream_call (Start: 2023-10-12 03:06:43.426, End: 2023-10-12 03:06:48.519)
  Operation: stream_generator (Start: 2023-10-12 03:06:43.425, End: 2023-10-12 03:06:48.519)
Operation: DB-GPT-Web-Entry (Start: 2023-10-12 03:06:43.180, End: 2023-10-12 03:06:43.257)
+-------------------------------------------------------------------------------------------------------------------------------------------+
|                                                             Chat Trace Details                                                            |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|      Key       |                                                       Value Value                                                        |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|    trace_id    |                                           5d1900c3-5aad-4159-9946-fbb600666530                                           |
|    span_id     |                        5d1900c3-5aad-4159-9946-fbb600666530:14772034-bed4-4b4e-b43f-fcf3a8aad6a7                         |
|    conv_uid    |                                           5e456272-68ac-11ee-9fba-0242ac150003                                           |
|   user_input   |                                                       Who are you?                                                       |
|   chat_mode    |                                                       chat_normal                                                        |
|  select_param  |                                                           None                                                           |
|   model_name   |                                                     vicuna-13b-v1.5                                                      |
|  temperature   |                                                           0.6                                                            |
| max_new_tokens |                                                           1024                                                           |
|      echo      |                                                          False                                                           |
|  llm_adapter   |                        FastChatLLMModelAdaperWrapper(fastchat.model.model_adapter.VicunaAdapter)                         |
|  User prompt   | A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polit |
|                |                             e answers to the user's questions. USER: Who are you? ASSISTANT:                             |
|  Model output  |  You can call me Vicuna, and I was trained by Large Model Systems Organization (LMSYS) researchers as a language model.  |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
```

### Viewing Chat Details Based on trace_id

```bash
dbgpt trace chat --hide_run_params --trace_id ec30d733-7b35-4d61-b02e-2832fd2e29ff
```

You will see an output like:

```
+-------------------------------------------------------------------------------------------------------------------------------------------+
|                                                             Chat Trace Details                                                            |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|      Key       |                                                       Value Value                                                        |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
|    trace_id    |                                           ec30d733-7b35-4d61-b02e-2832fd2e29ff                                           |
|    span_id     |                        ec30d733-7b35-4d61-b02e-2832fd2e29ff:0482a0c5-38b3-4b38-8101-e42489f90ccd                         |
|    conv_uid    |                                           87a722de-68ae-11ee-9fba-0242ac150003                                           |
|   user_input   |                                                          Hello                                                           |
|   chat_mode    |                                                       chat_normal                                                        |
|  select_param  |                                                           None                                                           |
|   model_name   |                                                     vicuna-13b-v1.5                                                      |
|  temperature   |                                                           0.6                                                            |
| max_new_tokens |                                                           1024                                                           |
|      echo      |                                                          False                                                           |
|  llm_adapter   |                        FastChatLLMModelAdaperWrapper(fastchat.model.model_adapter.VicunaAdapter)                         |
|  User prompt   | A chat between a curious user and an artificial intelligence assistant. The assistant gives helpful, detailed, and polit |
|                |                                e answers to the user's questions. USER: Hello ASSISTANT:                                 |
|  Model output  | Hello! How can I help you today? Is there something specific you want to know or talk about? I'm here to answer any ques |
|                |                                     tions you might have, to the best of my ability.                                     |
+----------------+--------------------------------------------------------------------------------------------------------------------------+
```

### More `chat` Usage

```bash
dbgpt trace chat --help
```

```
Usage: dbgpt trace chat [OPTIONS] [FILES]...

  Show conversation details

Options:
  --trace_id TEXT                 Specify the trace ID to analyze. If None,
                                  show latest conversation details
  --tree                          Display trace spans as a tree
  --hide_conv                     Hide your conversation details
  --hide_run_params               Hide run params
  --output [text|html|csv|latex|json]
                                  The output format
  --help                          Show this message and exit.
```

## Viewing Call Tree Based on `trace_id`

```bash
dbgpt trace tree --trace_id ec30d733-7b35-4d61-b02e-2832fd2e29ff
```

You will see an output like:

```
Operation: DB-GPT-Web-Entry (Start: 2023-10-12 03:22:10.592, End: None)
  Operation: get_chat_instance (Start: 2023-10-12 03:22:10.594, End: None)
  Operation: get_chat_instance (Start: 2023-10-12 03:22:10.594, End: 2023-10-12 03:22:10.658)
  Operation: stream_generator (Start: 2023-10-12 03:22:10.659, End: None)
    Operation: BaseChat.stream_call (Start: 2023-10-12 03:22:10.659, End: None)
      Operation: WorkerManager.generate_stream (Start: 2023-10-12 03:22:10.660, End: None)
        Operation: DefaultModelWorker.generate_stream (Start: 2023-10-12 03:22:10.675, End: None)
          Operation: DefaultModelWorker_call.generate_stream_func (Start: 2023-10-12 03:22:10.676, End: None)
          Operation: DefaultModelWorker_call.generate_stream_func (Start: 2023-10-12 03:22:10.676, End: 2023-10-12 03:22:16.130)
        Operation: DefaultModelWorker.generate_stream (Start: 2023-10-12 03:22:10.675, End: 2023-10-12 03:22:16.130)
      Operation: WorkerManager.generate_stream (Start: 2023-10-12 03:22:10.660, End: 2023-10-12 03:22:16.130)
    Operation: BaseChat.stream_call (Start: 2023-10-12 03:22:10.659, End: 2023-10-12 03:22:16.130)
  Operation: stream_generator (Start: 2023-10-12 03:22:10.659, End: 2023-10-12 03:22:16.130)
Operation: DB-GPT-Web-Entry (Start: 2023-10-12 03:22:10.592, End: 2023-10-12 03:22:10.673)
```


## Listing Trace Information

### Listing All Trace Information


```bash
dbgpt trace list
```

You will see an output like:
```
+--------------------------------------+---------------------------------------------------------------------------+-----------------------------------+------------------+
|               Trace ID               |                                  Span ID                                  |           Operation Name          | Conversation UID |
+--------------------------------------+---------------------------------------------------------------------------+-----------------------------------+------------------+
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:f650065f-f761-4790-99f7-8109c15f756a |           run_webserver           |       None       |
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:b2ff279e-0557-4b2d-8959-85e25dcfe94e |        EmbeddingLoader.load       |       None       |
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:b2ff279e-0557-4b2d-8959-85e25dcfe94e |        EmbeddingLoader.load       |       None       |
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:3e8b1b9d-5ef2-4382-af62-6b2b21cc04fd | WorkerManager._start_local_worker |       None       |
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:3e8b1b9d-5ef2-4382-af62-6b2b21cc04fd | WorkerManager._start_local_worker |       None       |
| eaf4830f-976f-45a4-9a50-244f3ab6f9e1 | eaf4830f-976f-45a4-9a50-244f3ab6f9e1:4c280ec9-0fd6-4ee8-b79f-1afcab0f9901 |      DefaultModelWorker.start     |       None       |
+--------------------------------------+---------------------------------------------------------------------------+-----------------------------------+------------------+
```

### Listing Trace Information by Trace Type

```bash
dbgpt trace list --span_type chat
```

You will see an output like:
```
+--------------------------------------+---------------------------------------------------------------------------+-------------------+--------------------------------------+
|               Trace ID               |                                  Span ID                                  |   Operation Name  |           Conversation UID           |
+--------------------------------------+---------------------------------------------------------------------------+-------------------+--------------------------------------+
| 5d1900c3-5aad-4159-9946-fbb600666530 | 5d1900c3-5aad-4159-9946-fbb600666530:14772034-bed4-4b4e-b43f-fcf3a8aad6a7 | get_chat_instance | 5e456272-68ac-11ee-9fba-0242ac150003 |
| 5d1900c3-5aad-4159-9946-fbb600666530 | 5d1900c3-5aad-4159-9946-fbb600666530:14772034-bed4-4b4e-b43f-fcf3a8aad6a7 | get_chat_instance | 5e456272-68ac-11ee-9fba-0242ac150003 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:0482a0c5-38b3-4b38-8101-e42489f90ccd | get_chat_instance | 87a722de-68ae-11ee-9fba-0242ac150003 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:0482a0c5-38b3-4b38-8101-e42489f90ccd | get_chat_instance | 87a722de-68ae-11ee-9fba-0242ac150003 |
+--------------------------------------+---------------------------------------------------------------------------+-------------------+--------------------------------------+
```

### Searching Trace Information

```bash
dbgpt trace list --search Hello
```

You will see an output like:
```
+--------------------------------------+---------------------------------------------------------------------------+----------------------------------------------+--------------------------------------+
|               Trace ID               |                                  Span ID                                  |                Operation Name                |           Conversation UID           |
+--------------------------------------+---------------------------------------------------------------------------+----------------------------------------------+--------------------------------------+
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:0482a0c5-38b3-4b38-8101-e42489f90ccd |              get_chat_instance               | 87a722de-68ae-11ee-9fba-0242ac150003 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:0482a0c5-38b3-4b38-8101-e42489f90ccd |              get_chat_instance               | 87a722de-68ae-11ee-9fba-0242ac150003 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:03de6c87-34d6-426a-85e8-7d46d475411e |             BaseChat.stream_call             |                 None                 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:03de6c87-34d6-426a-85e8-7d46d475411e |             BaseChat.stream_call             |                 None                 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:19593596-b4c7-4d15-a3c1-0924d86098dd | DefaultModelWorker_call.generate_stream_func |                 None                 |
| ec30d733-7b35-4d61-b02e-2832fd2e29ff | ec30d733-7b35-4d61-b02e-2832fd2e29ff:19593596-b4c7-4d15-a3c1-0924d86098dd | DefaultModelWorker_call.generate_stream_func |                 None                 |
+--------------------------------------+---------------------------------------------------------------------------+----------------------------------------------+--------------------------------------+
```

### More `list` Usage

```bash
dbgpt trace list --help
```

```
Usage: dbgpt trace list [OPTIONS] [FILES]...

  List your trace spans

Options:
  --trace_id TEXT                 Specify the trace ID to list
  --span_id TEXT                  Specify the Span ID to list.
  --span_type TEXT                Specify the Span Type to list.
  --parent_span_id TEXT           Specify the Parent Span ID to list.
  --search TEXT                   Search trace_id, span_id, parent_span_id,
                                  operation_name or content in metadata.
  -l, --limit INTEGER             Limit the number of recent span displayed.
  --start_time TEXT               Filter by start time. Format: "YYYY-MM-DD
                                  HH:MM:SS.mmm"
  --end_time TEXT                 Filter by end time. Format: "YYYY-MM-DD
                                  HH:MM:SS.mmm"
  --desc                          Whether to use reverse sorting. By default,
                                  sorting is based on start time.
  --output [text|html|csv|latex|json]
                                  The output format
  --help                          Show this message and exit.
```