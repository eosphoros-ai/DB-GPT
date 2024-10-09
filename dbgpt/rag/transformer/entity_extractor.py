"""EntityExtractor class."""

import logging
import re
from typing import List, Optional, Tuple

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)


class EntityExtractor(LLMExtractor):
    """
    EntityExtractor class for extracting medical entities and relationships from text.
    Inherits from LLMExtractor.
    """

    def __init__(self, llm_client: LLMClient, model_name: str, domain_knowledge_pt: str):
        """
        Initialize the EntityExtractor.

        Args:
            llm_client (LLMClient): The language model client.
            model_name (str): The name of the model to use.
            domain_knowledge_pt (str): The domain knowledge that provides context for entity extraction.
        """
        entity_extract_pt = ENTITY_EXTRACT_PT_EN.format(domain_knowledge_pt=domain_knowledge_pt)
        super().__init__(llm_client, model_name, entity_extract_pt)
        self.entities = set()
        self.triple_relationships = []

    def _parse_response(
        self, text: str, limit: Optional[int] = None
    ) -> List[Tuple[str, str, str]]:
        """
        Parse the LLM response and extract entities and relationships.

        Args:
            text (str): The response text from the LLM.
            limit (Optional[int]): The maximum number of relationships to extract.

        Returns:
            List[Tuple[str, str, str]]: A list of (entity1, relationship, entity2) tuples.
        """
        lines = text.split("\n")
        current_section = None
        entity_dict = {}
        relationship_list = []

        # Extract structured information (entities and relationships) from the LLM's response
        # while also implementing basic entity deduplication.
        for line in lines:
            line = line.strip()

            # Check if the line indicates a new section (Entities or Relationships)
            if line in ["Entities:", "Relationships:"]:
                # Set the current section, removing the colon
                current_section = line[:-1]
            elif line and current_section:
                # Process lines within a section
                if current_section == "Entities":
                    # Match the entity pattern: (name#type)
                    match = re.match(r"\((.*?)#(.*?)\)", line)
                    if match:
                        # Extract name and entity type
                        name, entity_type = [part.strip() for part in match.groups()]
                        # Add to entity_dict if not already present (case-insensitive)
                        if name.lower() not in entity_dict:
                            entity_dict[name.lower()] = (name, entity_type)
                elif current_section == "Relationships":
                    # Match the relationship pattern: (entity1#relation#entity2#description)
                    match = re.match(r"\((.*?)#(.*?)#(.*?)#(.*?)\)", line)
                    if match:
                        # Extract entity1, relation, entity2, and description
                        entity1, rel, entity2, description = [
                            part.strip() for part in match.groups()
                        ]
                        # Add the relationship to the list
                        relationship_list.append((entity1, rel, entity2, description))

        # Update the class attributes
        self.entities = set(entity_dict.values())

        # Create relationships with de-duplicated entities
        for entity1, rel, entity2, description in relationship_list:
            e1 = entity_dict.get(entity1.lower(), (entity1, "Unknown"))
            e2 = entity_dict.get(entity2.lower(), (entity2, "Unknown"))
            self.triple_relationships.append((e1[0], rel, e2[0]))

        if limit:
            return self.triple_relationships[:limit]
        return self.triple_relationships

    async def extract(
        self, text: str, limit: Optional[int] = None
    ) -> List[Tuple[str, str, str]]:
        """
        Extract entities and relationships from the given text.

        Args:
            text (str): The input text to extract from.
            limit (Optional[int]): The maximum number of relationships to extract.

        Returns:
            List[Tuple[str, str, str]]: A list of (entity1, relationship, entity2) tuples.
        """
        # Clear previous results
        self.entities.clear()
        self.triple_relationships.clear()

        return await super().extract(text, limit)
    
    def evaluate_recall(self, text: str, entities: List[Tuple[str, str]]) -> float:
        """
        Evaluate the recall rate of the entity extraction.

        Args:
            text (str): The input text to evaluate.
            entities (List[Tuple[str, str]]): The list of entities to evaluate.

        Returns:
            float: The recall rate of the entity extraction(0.0-1.0).
        """
        pass

    def get_entities(self) -> List[Tuple[str, str]]:
        """
        Get the list of unique entities extracted.

        Returns:
            List[Tuple[str, str]]: A list of (entity_name, entity_type) tuples.
        """
        return list(self.entities)

    def get_triple_relationships(self) -> List[Tuple[str, str, str]]:
        """
        Get the list of triple relationships extracted.

        Returns:
            List[Tuple[str, str, str]]: A list of (entity1, relationship, entity2) tuples.
        """
        return self.triple_relationships


ENTITY_EXTRACT_PT_EN = """
Task:
Extract entities and their relationships cohering the specific domain knowledge from the following text.

Domain knowledge:
{domain_knowledge_pt}

Format your response as follows (your response must include the brackets):

Entities:
(entity_name#entity_type)
(entity_name#entity_type)

Relationships:
(entity1#relationship#entity2#description)
(entity1#relationship#entity2#description)

Text:
{{text}}
"""
