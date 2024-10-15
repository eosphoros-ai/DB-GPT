"""Client: run evaluation example.

This example demonstrates how to use the dbgpt client to evaluate with the rag recall
and app answer.

Example:
    .. code-block:: python

        DBGPT_API_KEY = "dbgpt"
        client = Client(api_key=DBGPT_API_KEY)

        # 1. evaluate with rag recall
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
        # 2. evaluate with app answer
        request = EvaluateServeRequest(
            # The scene type of the evaluation, e.g. support app, recall
            scene_key="app",
            # e.g. app id(when scene_key is app), space id(when scene_key is recall)
            scene_value="2c76eea2-83b6-11ef-b482-acde48001122",
            "context"={
                "top_k": 5,
                "prompt": "942acd7e33b54ce28565f89f9b278044",
                "model": "zhipu_proxyllm",
            },
            evaluate_metrics=[
                "AnswerRelevancyMetric",
            ],
            datasets=[
                {
                    "query": "what awel talked about",
                    "doc_name": "awel.md",
                }
            ],
        )
        data = await run_evaluation(client, request=request)
        print(data)
"""

import asyncio

from dbgpt.client import Client
from dbgpt.client.evaluation import run_evaluation
from dbgpt.serve.evaluate.api.schemas import EvaluateServeRequest


async def main():
    # initialize client
    DBGPT_API_KEY = "dbgpt"
    SPACE_ID = "147"
    client = Client(api_key=DBGPT_API_KEY)
    request = EvaluateServeRequest(
        # The scene type of the evaluation, e.g. support app, recall
        scene_key="recall",
        # e.g. app id(when scene_key is app), space id(when scene_key is recall)
        scene_value=SPACE_ID,
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
    print(data)


if __name__ == "__main__":
    asyncio.run(main())
