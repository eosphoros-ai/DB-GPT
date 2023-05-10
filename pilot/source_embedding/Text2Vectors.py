from typing import List
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
import torch


device = "cuda" if torch.cuda.is_available() else "cpu"
from langchain.embeddings.base import Embeddings



class Text2Vectors(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""

    def embed_query(self, text: str) -> List[float]:
        hfemb = HuggingFaceEmbeddings(model_name="/Users/chenketing/Desktop/project/all-MiniLM-L6-v2")
        return hfemb.embed_documents(text)[0]