"""SimpleIntentTranslator class."""

import json
import logging
import re
from typing import Dict, List, Union

from dbgpt.core import BaseMessage, HumanPromptTemplate, LLMClient
from dbgpt.rag.transformer.llm_translator import LLMTranslator

INTENT_INTERPRET_PT = """
A question is provided below. Given the question, analyze and classify it into one of the following categories:
1. Single Entity Search: search for the detail of the given entity.
2. One Hop Entity Search: given one entity and one relation, search for all entities that have the relation with the given entity.
3. One Hop Relation Search: given two entities, search for the relation between them.
4. Two Hop Entity Search: given one entity and one relation, break that relation into two consecutive relation, then search all entities that have the two hop relation with the given entity.
5. Freestyle Question: questions that are not in above four categories. Search all related entities and two-hop sub-graphs centered on them.
After classified the given question, rewrite the question in a graph query language style, return the category of the given question, the rewrite question in json format.
Also return entities and relations that might be used for query generation in json format. Here are some examples to guide your classification:
---------------------
Example:
Question: Introduce TuGraph.
Return:
{{"category": "Single Entity Search", rewritten_question": "Query the entity named TuGraph then return the entity.", entities": ["TuGraph"], "relations": []}}
Question: Who commits code to TuGraph.
Return:
{{"category": "One Hop Entity Search", "rewritten_question": "Query all one hop paths that has a entity named TuGraph and a relation named commit, then return them.", "entities": ["TuGraph"], "relations": ["commit"]}}
Question: What is the relation between Alex and TuGraph?
Return:
{{"category": "One Hop Relation Search", "rewritten_question": "Query all one hop paths between the entity named Alex and the entity named TuGraph, then return them.", "entities": ["Alex", "TuGraph"], "relations": []}}
Question: Who is the colleague of Bob?
Return:
{{"category": "Two Hop Entity Search", "rewritten_question": "Query all entities that have a two hop path between them and the entity named Bob, both entities should have a work for relation with the middle entity.", "entities": ["Bob"], "relations": ["work for"]}}
Question: Introduce TuGraph and DB-GPT separately.
Return:
{{"category": "Freestyle Question", "rewritten_question": "Query the entity named TuGraph and the entity named DB-GPT, then return two-hop sub-graphs centered on them.", "entities": ["TuGraph", "DBGPT"], "relations": []}}
---------------------
Text: {text}
Return:

"""  # noqa: E501

logger = logging.getLogger(__name__)


class SimpleIntentTranslator(LLMTranslator):
    """SimpleIntentTranslator class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the SimpleIntentTranslator."""
        super().__init__(llm_client, model_name, INTENT_INTERPRET_PT)

    def _format_messages(self, text: str, history: str = None) -> List[BaseMessage]:
        # interprete intention with single prompt only.
        template = HumanPromptTemplate.from_template(self._prompt_template)

        messages: List[BaseMessage] = (
            template.format_messages(text=text, history=history)
            if history is not None
            else template.format_messages(text=text)
        )

        return messages

    def truncate(self):
        """Do nothing by default."""

    def drop(self):
        """Do nothing by default."""

    def _parse_response(self, text: str) -> Dict:
        """
        Parse llm response.

        The returned diction should contain the following content.
        {
            "category": "Type of the given question.",
            "original_question: "The original question provided by user.",
            "rewritten_question": "Rewritten question in graph query language style."
            "entities": ["entities", "that", "might", "be", "used", "in", "query"],
            "relations" ["relations", "that", "might", "be", "used", "in", "query"]
        }
        """
        code_block_pattern = re.compile(r"```json(.*?)```", re.S)
        json_pattern = re.compile(r"{.*?}", re.S)

        match_result = re.findall(code_block_pattern, text)
        if match_result:
            text = match_result[0]
        match_result = re.findall(json_pattern, text)
        if match_result:
            text = match_result[0]
        else:
            text = ""

        intention: Dict[str, Union[str, List[str]]] = {}
        intention = json.loads(text)
        if "category" not in intention:
            intention["category"] = ""
        if "original_question" not in intention:
            intention["original_question"] = ""
        if "rewritten_question" not in intention:
            intention["rewritten_question"] = ""
        if "entities" not in intention:
            intention["entities"] = []
        if "relations" not in intention:
            intention["relations"] = []

        return intention
