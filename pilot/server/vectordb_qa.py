#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain.prompts import PromptTemplate

from pilot.configs.config import Config
from pilot.conversation import conv_qa_prompt_template, conv_db_summary_templates
from pilot.logs import logger
from pilot.model.llm_out.vicuna_llm import VicunaLLM
from pilot.vector_store.file_loader import KnownLedge2Vector

CFG = Config()


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
            search_kwargs={"k": CFG.KNOWLEDGE_SEARCH_TOP_SIZE}
        )
        docs = retriever.get_relevant_documents(query=query)

        context = [d.page_content for d in docs]
        result = prompt.format(context="\n".join(context), question=query)
        return result

    @staticmethod
    def build_knowledge_prompt(query, docs, state):
        prompt_template = PromptTemplate(
            template=conv_qa_prompt_template, input_variables=["context", "question"]
        )
        context = [d.page_content for d in docs]
        result = prompt_template.format(context="\n".join(context), question=query)
        state.messages[-2][1] = result
        prompt = state.get_prompt()

        if len(prompt) > 4000:
            logger.info("prompt length greater than 4000, rebuild")
            context = context[:2000]
            prompt_template = PromptTemplate(
                template=conv_qa_prompt_template,
                input_variables=["context", "question"],
            )
            result = prompt_template.format(context="\n".join(context), question=query)
            state.messages[-2][1] = result
            prompt = state.get_prompt()
            print("new prompt length:" + str(len(prompt)))

        return prompt

    @staticmethod
    def build_db_summary_prompt(query, db_profile_summary, state):
        prompt_template = PromptTemplate(
            template=conv_db_summary_templates,
            input_variables=["db_input", "db_profile_summary"],
        )
        # context = [d.page_content for d in docs]
        result = prompt_template.format(
            db_profile_summary=db_profile_summary, db_input=query
        )
        state.messages[-2][1] = result
        prompt = state.get_prompt()
        return prompt
