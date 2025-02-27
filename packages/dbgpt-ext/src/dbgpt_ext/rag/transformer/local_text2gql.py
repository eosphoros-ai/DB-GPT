"""LocalText2GQL class."""

import json
import logging
import re
from typing import Dict, List, Union

from dbgpt.core import BaseMessage, HumanPromptTemplate
from dbgpt.model.proxy.llms.ollama import OllamaLLMClient
from dbgpt.rag.transformer.llm_translator import LLMTranslator

LOCAL_TEXT_TO_GQL_PT = """
A question written in graph query language style is provided below. Given the question, translate the question into a cypher query that can be executed on the given knowledge graph. Make sure the syntax of the translated cypher query is correct.
To help query generation, the schema of the knowledge graph is:
{schema}
---------------------
Question: {question}
Query:

"""  # noqa: E501

logger = logging.getLogger(__name__)


class LocalText2GQL(LLMTranslator):
    """LocalText2GQL class."""

    def __init__(self, model_name: str):
        """Initialize the LocalText2GQL."""
        super().__init__(OllamaLLMClient(), model_name, LOCAL_TEXT_TO_GQL_PT)

    def _format_messages(self, text: str, history: str = None) -> List[BaseMessage]:
        # translate intention to gql with single prompt only.
        intention: Dict[str, Union[str, List[str]]] = json.loads(text)
        question = intention.get("rewritten_question", "")
        schema = intention.get("schema", "")

        template = HumanPromptTemplate.from_template(self._prompt_template)

        messages = (
            template.format_messages(
                schema=schema,
                question=question,
                history=history,
            )
            if history is not None
            else template.format_messages(
                schema=schema,
                question=question,
            )
        )

        return messages

    def _parse_response(self, text: str) -> Dict:
        """Parse llm response."""
        translation: Dict[str, str] = {}
        query = ""

        code_block_pattern = re.compile(r"```cypher(.*?)```", re.S)

        result = re.findall(code_block_pattern, text)
        if result:
            query = result[0]
        else:
            query = text

        translation["query"] = query.strip()

        return translation
