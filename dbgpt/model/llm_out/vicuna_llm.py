#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
from typing import Any, List, Mapping, Optional
from urllib.parse import urljoin

import requests
from langchain.embeddings.base import Embeddings
from langchain.llms.base import LLM
from dbgpt._private.pydantic import BaseModel

from dbgpt._private.config import Config

CFG = Config()


class VicunaLLM(LLM):
    vicuna_generate_path = "generate_stream"

    def _call(
        self,
        prompt: str,
        temperature: float,
        max_new_tokens: int,
        stop: Optional[List[str]] = None,
    ) -> str:
        params = {
            "prompt": prompt,
            "temperature": temperature,
            "max_new_tokens": max_new_tokens,
            "stop": stop,
        }
        response = requests.post(
            url=urljoin(CFG.MODEL_SERVER, self.vicuna_generate_path),
            data=json.dumps(params),
        )

        skip_echo_len = len(params["prompt"]) + 1 - params["prompt"].count("</s>") * 3
        for chunk in response.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                data = json.loads(chunk.decode())
                if data["error_code"] == 0:
                    output = data["text"][skip_echo_len:].strip()
                    yield output

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
            url=urljoin(CFG.MODEL_SERVER, self.vicuna_embedding_path),
            json={"prompt": p},
        )
        response.raise_for_status()
        return response.json()["response"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Call out to Vicuna's server embedding endpoint for embedding search docs.

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
        """Call out to Vicuna's server embedding endpoint for embedding query text.

        Args:
            text: The text to embed.
        Returns:
            Embedding for the text
        """
        embedding = self._call(text)
        return embedding
