#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pilot.vector_store.file_loader import KnownLedge2Vector
from langchain.prompts import PromptTemplate
from pilot.conversation import conv_qk_prompt_template
from langchain.chains import RetrievalQA
from pilot.configs.model_config import VECTOR_SEARCH_TOP_K

class KnownLedgeBaseQA:

    llm: object = None

    def __init__(self) -> None:
        k2v = KnownLedge2Vector()
        self.vector_store = k2v.init_vector_store()
    
    def get_answer(self, query):
        prompt_template = conv_qk_prompt_template
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        knownledge_chain = RetrievalQA.from_llm(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(search_kwargs={"k", VECTOR_SEARCH_TOP_K}),
            prompt=prompt
        )
        knownledge_chain.return_source_documents = True
        result = knownledge_chain({"query": query})
        yield result
