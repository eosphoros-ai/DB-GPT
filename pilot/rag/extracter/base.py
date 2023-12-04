from abc import abstractmethod, ABC
from typing import List, Dict

from langchain.schema import Document


class Extractor(ABC):
    """Extractor Base class, it's apply for Summary Extractor, Keyword Extractor, Triplets Extractor, Question Extractor, etc."""

    def __init__(self):
        pass

    @abstractmethod
    def extract(self, chunks: List[Document]) -> List[Dict]:
        """Extracts chunks.

        Args:
            nodes (Sequence[Document]): nodes to extract metadata from
        """
