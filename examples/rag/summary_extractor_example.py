"""Summary extractor example.
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
            python examples/rag/summary_extractor_example.py
"""


import asyncio
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import SummaryAssembler
from dbgpt.rag.knowledge import KnowledgeFactory


async def main():
    file_path = os.path.join(ROOT_PATH, "docs/docs/awel/awel.md")
    llm_client = OpenAILLMClient()
    knowledge = KnowledgeFactory.from_file_path(file_path)
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    assembler = SummaryAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        llm_client=llm_client,
        model_name="gpt-3.5-turbo",
    )
    return await assembler.generate_summary()


if __name__ == "__main__":
    output = asyncio.run(main())
    print(f"output: \n\n{output}")
