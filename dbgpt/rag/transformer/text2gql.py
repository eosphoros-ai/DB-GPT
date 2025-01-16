"""Text2GQL class."""
import json
import logging
import re
from typing import Dict, List, Union

from dbgpt.core import BaseMessage, HumanPromptTemplate, LLMClient
from dbgpt.rag.transformer.llm_translator import LLMTranslator

TEXT_TO_GQL_PT = (
    "A question written in graph query language style is provided below. "
    "The category of this question, "
    "entities and relations that might be used in the cypher query are also provided. "
    "Given the question, translate the question into a cypher query that "
    "can be executed on the given knowledge graph. "
    "Make sure the syntax of the translated cypher query is correct.\n"
    "To help query generation, the schema of the knowledge graph is:\n"
    "{schema}\n"
    "---------------------\n"
    "Example:\n"
    "Question: Query the entity named TuGraph then return the entity.\n"
    "Category: Single Entity Search\n"
    'entities: ["TuGraph"]\n'
    "relations: []\n"
    'Query:\nMatch (n) WHERE n.id="TuGraph" RETURN n\n'
    "Question: Query all one hop paths between the entity named Alex "
    "and the entity named TuGraph, then return them.\n"
    "Category: One Hop Entity Search\n"
    'entities: ["Alex", "TuGraph"]\n'
    "relations: []\n"
    'Query:\nMATCH p=(n)-[r]-(m) WHERE n.id="Alex" AND m.id="TuGraph" RETURN p \n'
    "Question: Query all one hop paths that has a entity named TuGraph "
    "and a relation named commit, then return them.\n"
    "Category: One Hop Relation Search\n"
    'entities: ["TuGraph"]\n'
    'relations: ["commit"]\n'
    'Query:\nMATCH p=(n)-[r]-(m) WHERE n.id="TuGraph" AND r.id="commit" RETURN p \n'
    "Question: Query all entities that have a two hop path between them "
    "and the entity named Bob, "
    "both entities should have a work for relation with the middle entity.\n"
    "Category: Two Hop Entity Search\n"
    'entities: ["Bob"]\n'
    'relations: ["work for"]\n'
    'Query:\nMATCH p=(n)-[r1]-(m)-[r2]-(l) WHERE n.id="Bob" '
    'AND r1.id="work for" AND r2.id="work for" RETURN p \n'
    "Question: Introduce TuGraph and DBGPT seperately.\n"
    "Category: Freestyle Question\n"
    'entities: ["TuGraph", "DBGPT"]\n'
    "relations: []\n"
    "Query:\nMATCH p=(n)-[r:relation*2]-(m) "
    'WHERE n.id IN ["TuGraph", "DB-GPT"] RETURN p\n'
    "---------------------\n"
    "Question: {question}\n"
    "Category: {category}\n"
    "entities: {entities}\n"
    "relations: {relations}\n"
    "Query:\n"
)

logger = logging.getLogger(__name__)


class Text2GQL(LLMTranslator):
    """Text2GQL class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the Text2GQL."""
        super().__init__(llm_client, model_name, TEXT_TO_GQL_PT)

    def _format_messages(self, text: str, history: str = None) -> List[BaseMessage]:
        # translate intention to gql with single prompt only.
        intention: Dict[str, Union[str, List[str]]] = json.loads(text)
        question = intention.get("rewritten_question", "")
        category = intention.get("category", "")
        entities = intention.get("entities", "")
        relations = intention.get("relations", "")
        schema = intention.get("schema", "")

        template = HumanPromptTemplate.from_template(self._prompt_template)

        messages = (
            template.format_messages(
                schema=schema,
                question=question,
                category=category,
                entities=entities,
                relations=relations,
                history=history,
            )
            if history is not None
            else template.format_messages(
                schema=schema,
                question=question,
                category=category,
                entities=entities,
                relations=relations,
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
