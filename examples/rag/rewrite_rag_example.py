"""Query rewrite example.

    pre-requirements:
        1. install openai python sdk
        ```
            pip install openai
        ```
        2. set openai key and base
        ```
            export OPENAI_API_KEY={your_openai_key}
            export OPENAI_API_BASE={your_openai_base}
        ```
        or
        ```
            import os
            os.environ["OPENAI_API_KEY"] = {your_openai_key}
            os.environ["OPENAI_API_BASE"] = {your_openai_base}
        ```
    Examples:
        ..code-block:: shell
            python examples/rag/rewrite_rag_example.py
"""

import asyncio

from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag.retriever import QueryRewrite


async def main():
    query = "compare steve curry and lebron james"
    llm_client = OpenAILLMClient()
    reinforce = QueryRewrite(
        llm_client=llm_client,
        model_name="gpt-3.5-turbo",
    )
    return await reinforce.rewrite(origin_query=query, nums=1)


if __name__ == "__main__":
    output = asyncio.run(main())
    print(f"output: \n\n{output}")
