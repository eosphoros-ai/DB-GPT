#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain.prompts import PromptTemplate

from pilot.configs.model_config import VECTOR_SEARCH_TOP_K
from pilot.conversation import conv_qa_prompt_template
from pilot.model.vicuna_llm import VicunaLLM
from pilot.vector_store.file_loader import KnownLedge2Vector


class KnownLedgeBaseQA:
    def __init__(self) -> None:
        k2v = KnownLedge2Vector()
        self.vector_store = k2v.init_vector_store()
        self.llm = VicunaLLM()

    def get_similar_answer(self, query):
        prompt = PromptTemplate(
            template=conv_qa_prompt_template, input_variables=["context", "question"]
        )

        retriever = self.vector_store.as_retriever(
            search_kwargs={"k": VECTOR_SEARCH_TOP_K}
        )
        docs = retriever.get_relevant_documents(query=query)

        context = [d.page_content for d in docs]
        result = prompt.format(context="\n".join(context), question=query)
        return result
