# Datasets Benchmark

Get started with the Benchmark API


### Create Dataset Benchmark Task

```python
POST /api/v2/serve/evaluate/execute_benchmark_task
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X POST "http://localhost:5670/api/v2/serve/evaluate/execute_benchmark_task" \
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json" \
-d '{
    "scene_value": "Falcon_benchmark_01",
    "model_list": ["DeepSeek-V3.1", "Qwen3-235B-A22B"]
}'

```

#### The Benchmark Request Object

________
<b>scene_key</b> <font color="gray"> string </font> <font color="red"> Required </font>

The scene type of the evaluation, e.g. support app, recall

--------
<b>scene_value</b> <font color="gray"> string </font> <font color="red"> Required </font>

The scene value of the benchmark, e.g. The marking evaluation task name

--------
<b>model_list</b> <font color="gray"> object </font> <font color="red"> Required </font>

The model name list of the benchmark will execute, e.g. ["DeepSeek-V3.1","Qwen3-235B-A22B"]
Notice: The model name configured on the db-gpt platform needs to be entered.

--------
<b>temperature</b> <font color="gray"> float </font>

The temperature of the llm model, Default is 0.7

--------
<b>max_tokens</b> <font color="gray"> int </font>

The max tokens of the llm model, Default is None

--------


#### The Benchmark Result

________
<b>status</b> <font color="gray">string</font>

The benchmark status，e.g. success, failed, running
________


### Query Benchmark Task List

```python
GET /api/v2/serve/evaluate/benchmark_task_list
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/evaluate/benchmark_task_list?page=1&page_size=20" \ 
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json"

```

#### The Benchmark Task List Request Object

________
<b>page</b> <font color="gray"> string </font> <font color="red"> Required </font>

Query task list page number, Default is 1

--------
<b>page_size</b> <font color="gray"> string </font> <font color="red"> Required </font>

Query task list page size, Default is 20

--------


#### The Benchmark Task List Result

```json
{
    "success": true,
    "err_code": null,
    "err_msg": null,
    "data": {
        "items": [
            {
                "evaluate_code": "1ec15dcbf5d54124bd5a5d23992af35d",
                "scene_key": "dataset",
                "scene_value": "local_benchmark_task_for_Qwen",
                "datasets_name": "Falcon评测集",
                "input_file_path": "2025_07_27_public_500_standard_benchmark_question_list.xlsx",
                "output_file_path": "/DB-GPT/pilot/benchmark_meta_data/result/1ec15dcbf5d54124bd5a5d23992af35d/202510201650_multi_round_benchmark_result.xlsx",
                "model_list": [
                    "Qwen3-Coder-480B-A35B-Instruct"
                ],
                "context": {
                    "benchmark_config": "{\"file_parse_type\":\"EXCEL\", \"format_type\":\"TEXT\", \"content_type\":\"SQL\", \"benchmark_mode_type\":\"EXECUTE\", \"scene_key\":\"dataset\", \"temperature\":0.6, \"max_tokens\":6000}"
                },
                "user_name": null,
                "user_id": null,
                "sys_code": "benchmark_system",
                "parallel_num": 1,
                "state": "running",
                "temperature": null,
                "max_tokens": null,
                "log_info": null,
                "gmt_create": "2025-10-20 16:50:46",
                "gmt_modified": "2025-10-20 16:50:46",
                "cost_time": null,
                "round_time": 1
            }
        ],
        "total_count": 80,
        "total_pages": 4,
        "page": 1,
        "page_size": 20
    }
}
```

________
<b>evaluate_code</b> <font color="gray">string</font>

The benchmark task unique code
________
<b>scene_key</b> <font color="gray">string</font>

The benchmark task scene, e.g. dataset
________
<b>scene_value</b> <font color="gray">string</font>

The benchmark task name
________
<b>datasets_name</b> <font color="gray">string</font>

The benchmark execute dataset name
________
<b>input_file_path</b> <font color="gray">string</font>

The benchmark dataset file path
________
<b>output_file_path</b> <font color="gray">string</font>

The benchmark execute result file path
________
<b>model_list</b> <font color="gray">object</font>

The benchmark execute model list
________
<b>context</b> <font color="gray">object</font>

The benchmark task context
________
<b>user_name</b> <font color="gray">string</font>

The benchmark task user name
________
<b>user_id</b> <font color="gray">string</font>

The benchmark task user id
________
<b>sys_code</b> <font color="gray">string</font>

The benchmark task system code, e.g. benchmark_system
________
<b>parallel_num</b> <font color="gray">int</font>

The benchmark task execute parallel num 
________
<b>state</b> <font color="gray">string</font>

The benchmark task state, e.g. running, success, failed
________
<b>temperature</b> <font color="gray">float</font>

The benchmark task LLM temperature
________
<b>max_tokens</b> <font color="gray">int</font>

The benchmark task LLM max tokens
________
<b>log_info</b>  <font color="gray">int</font>

If benchmark task execute error, It will show error message, 
________
<b>gmt_create</b> <font color="gray">string</font>

Task create time
________
<b>gmt_modified</b> <font color="gray">string</font>

Task Finish time
________
<b>cost_time</b> <font color="gray">int</font>

Benchmark Task cost time
________
<b>round_time</b> <font color="gray">int</font>

Benchmark Task execute round time
________


### Benchmark Compare Result

```python
GET /api/v2/serve/evaluate/benchmark/result/{evaluate_code}
```

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/evaluate/benchmark/result/{evaluate_code}" \
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json"

```

#### The Benchmark Request Object

________
<b>evaluate_code</b> <font color="gray"> string </font> <font color="red"> Required </font>

The benchMark task unique code

--------

#### The Benchmark Result

```json
{
    "success": true,
    "err_code": null,
    "err_msg": null,
    "data": {
        "evaluate_code": "c827a274b4084f5dbce4c630f5267239",
        "scene_value": "Falcon评测集_benchmark",
        "summaries": [
            {
                "roundId": 1,
                "llmCode": "Qwen3-Coder-480B-A35B-Instruct",
                "right": 136,
                "wrong": 269,
                "failed": 95,
                "exception": 0,
                "accuracy": 0.272,
                "execRate": 0.81,
                "outputPath": "/DB-GPT/pilot/benchmark_meta_data/result/c827a274b4084f5dbce4c630f5267239/202510181449_multi_round_benchmark_result.xlsx"
            }
        ]
    }
}
```

________
<b>roundId</b> <font color="gray">string</font>

The benchmark task execute round time
________
<b>llmCode</b> <font color="gray">string</font>

The benchmark task execute model name
________
<b>right</b> <font color="gray">int</font>
The benchmark task execute right question number
________
<b>wrong</b> <font color="gray">int</font>
The benchmark task execute wrong question number
________
<b>failed</b> <font color="gray">int</font>
The benchmark task execute failed question number
________
<b>exception</b> <font color="gray">int</font>
The benchmark task execute exception question number
________
<b>accuracy</b> <font color="gray">float</font>
The benchmark task question list execute accuracy rate
________
<b>execRate</b> <font color="gray">float</font>
The benchmark task question list executable rate
________
<b>outputPath</b> <font color="gray">string</font>
The benchmark task execute result output file path
________

