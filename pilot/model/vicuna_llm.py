#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import requests
from urllib.parse import urljoin
from langchain.embeddings.base import Embeddings
from pydantic import BaseModel
from typing import Any, Mapping, Optional, List
from langchain.llms.base import LLM
from configs.model_config import *

class VicunaRequestLLM(LLM):

    vicuna_generate_path = "generate"
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        if isinstance(stop, list):
            stop = stop + ["Observation:"]
        
        skip_echo_len = len(prompt.replace("</s>", " ")) + 1
        params = {
            "prompt": prompt,
            "temperature": 0.7,
            "max_new_tokens": 1024,
            "stop": stop
        }
        response = requests.post(
            url=urljoin(vicuna_model_server, self.vicuna_generate_path),
            data=json.dumps(params),
        )
        response.raise_for_status()
        # for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        #     if chunk:
        #         data = json.loads(chunk.decode())
        #         if data["error_code"] == 0:
        #             output = data["text"][skip_echo_len:].strip()
        #             output = self.post_process_code(output)
        #             yield output
        return response.json()["response"]

    @property
    def _llm_type(self) -> str:
        return "custome"

    def _identifying_params(self) -> Mapping[str, Any]:
        return {}
    

class VicunaEmbeddingLLM(BaseModel, Embeddings):
    
    vicuna_embedding_path = "embedding"

    def _call(self, prompt: str) -> str:
        p = prompt.strip()
        print("Sending prompt ", p)

        response = requests.post(
            url=urljoin(vicuna_model_server, self.vicuna_embedding_path),
            json={
                "prompt": p
            }
        )
        response.raise_for_status()
        return response.json()["response"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """ Call out to Vicuna's server embedding endpoint for embedding search docs.

        Args:
            texts: The list of text to embed

        Returns:
            List of embeddings. one for each text.
        """
        results = []
        for text in texts:
            response = self.embed_query(text)
            results.append(response)
        return results 
    

    def embed_query(self, text: str) -> List[float]:
        """ Call out to Vicuna's server embedding endpoint for embedding query text.
        
        Args: 
            text: The text to embed.
        Returns:
            Embedding for the text
        """
        embedding = self._call(text)
        return embedding

