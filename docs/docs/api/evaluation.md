# Evaluation

Get started with the Evaluation API


### Create Evaluation

```python
POST /api/v2/serve/evaluate/evaluation
```
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="curl_evaluation"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_evaluation'},
    {label: 'Python', value: 'python_evaluation'},
  ]
}>

<TabItem value="curl_evaluation">

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}

curl -X POST "http://localhost:5670/api/v2/serve/evaluate/evaluation" 
-H "Authorization: Bearer $DBGPT_API_KEY" \
-H "accept: application/json" \
-H "Content-Type: application/json" \
-d '{
  "scene_key": "recall",
  "scene_value":147,
  "context":{"top_k":5},
  "sys_code":"xx",
  "evaluate_metrics":["RetrieverHitRateMetric","RetrieverMRRMetric","RetrieverSimilarityMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}'

```
 </TabItem>

<TabItem value="python_evaluation">


```python
from dbgpt.client import Client
from dbgpt.client.evaluation import run_evaluation
from dbgpt.serve.evaluate.api.schemas import EvaluateServeRequest

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)
request = EvaluateServeRequest(
    # The scene type of the evaluation, e.g. support app, recall
    scene_key="recall",
    # e.g. app id(when scene_key is app), space id(when scene_key is recall)
    scene_value="147",
    context={"top_k": 5},
    evaluate_metrics=[
        "RetrieverHitRateMetric",
        "RetrieverMRRMetric",
        "RetrieverSimilarityMetric",
    ],
    datasets=[
        {
            "query": "what awel talked about",
            "doc_name": "awel.md",
        }
    ],
)
data = await run_evaluation(client, request=request)

```

 </TabItem>
</Tabs>

#### Request body
Request <a href="#the-evaluation-request">Evaluation Object</a>

when scene_key is app, the request body should be like this:
```json

{
  "scene_key": "app",
  "scene_value":"2c76eea2-83b6-11ef-b482-acde48001122",
  "context":{"top_k":5, "prompt":"942acd7e33b54ce28565f89f9b278044","model":"zhipu_proxyllm"},
  "sys_code":"xx",
  "evaluate_metrics":["AnswerRelevancyMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}
```

when scene_key is recall, the request body should be like this:
```json

{
  "scene_key": "recall",
  "scene_value":"2c76eea2-83b6-11ef-b482-acde48001122",
  "context":{"top_k":5, "prompt":"942acd7e33b54ce28565f89f9b278044","model":"zhipu_proxyllm"},
  "evaluate_metrics":["RetrieverHitRateMetric", "RetrieverMRRMetric", "RetrieverSimilarityMetric"],
  "datasets": [{
            "query": "what awel talked about",
            "doc_name":"awel.md"
        }]
}
```

#### Response body
Return <a href="#the-evaluation-object">Evaluation Object</a> List 


### The Evaluation Request Object

________
<b>scene_key</b> <font color="gray"> string </font> <font color="red"> Required </font>

The scene type of the evaluation, e.g. support app, recall

--------
<b>scene_value</b> <font color="gray"> string </font> <font color="red"> Required </font>

The scene value of the evaluation, e.g. app id(when scene_key is app), space id(when scene_key is recall)

--------
<b>context</b> <font color="gray"> object </font> <font color="red"> Required </font>

The context of the evaluation
- top_k <font color="gray"> int </font> <font color="red"> Required </font>
- prompt <font color="gray"> string </font> prompt code
- model <font color="gray"> string </font> llm model name

--------
evaluate_metrics <font color="gray"> array </font> <font color="red"> Required </font>

The evaluate metrics of the evaluation, 
e.g. 
- <b>AnswerRelevancyMetric</b>: the answer relevancy metric(when scene_key is app)
- <b>RetrieverHitRateMetric</b>: Hit rate calculates the fraction of queries where the correct answer is found
    within the top-k retrieved documents. In simpler terms, it’s about how often our
    system gets it right within the top few guesses. (when scene_key is recall)
- <b>RetrieverMRRMetric</b>: For each query, MRR evaluates the system’s accuracy by looking at the rank of the
    highest-placed relevant document. Specifically, it’s the average of the reciprocals
    of these ranks across all the queries. So, if the first relevant document is the
    top result, the reciprocal rank is 1; if it’s second, the reciprocal rank is 1/2,
    and so on. (when scene_key is recall)
- <b>RetrieverSimilarityMetric</b>: Embedding Similarity Metric (when scene_key is recall)

--------
datasets <font color="gray"> array </font> <font color="red"> Required </font>


The datasets of the evaluation


--------


### The Evaluation Result

________
<b>prediction</b> <font color="gray">string</font>

The prediction result
________
<b>contexts</b> <font color="gray">string</font>

The contexts of RAG Retrieve chunk
________
<b>score</b> <font color="gray">float</font>

The score of the prediction
________
<b>passing</b> <font color="gray">bool</font>

The passing of the prediction
________
<b>metric_name</b> <font color="gray">string</font>

The metric name of the evaluation
________
<b>prediction_cost</b> <font color="gray">int</font>

The prediction cost of the evaluation
________
<b>query</b> <font color="gray">string</font>

The query of the evaluation
________
<b>raw_dataset</b> <font color="gray">object</font>

The raw dataset of the evaluation
________
<b>feedback</b> <font color="gray">string</font>

The feedback of the llm evaluation
________
