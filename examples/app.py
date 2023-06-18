#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import gradio as gr
from langchain.agents import AgentType, initialize_agent, load_tools
from llama_index import (
    Document,
    GPTVectorStoreIndex,
    LangchainEmbedding,
    LLMPredictor,
    ServiceContext,
)

from pilot.model.llm_out.vicuna_llm import VicunaEmbeddingLLM, VicunaRequestLLM


def agent_demo():
    llm = VicunaRequestLLM()

    tools = load_tools(["python_repl"], llm=llm)
    agent = initialize_agent(
        tools, llm, agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True
    )
    agent.run("Write a SQL script that Query 'select count(1)!'")


def knowledged_qa_demo(text_list):
    llm_predictor = LLMPredictor(llm=VicunaRequestLLM())
    hfemb = VicunaEmbeddingLLM()
    embed_model = LangchainEmbedding(hfemb)
    documents = [Document(t) for t in text_list]

    service_context = ServiceContext.from_defaults(
        llm_predictor=llm_predictor, embed_model=embed_model
    )
    index = GPTVectorStoreIndex.from_documents(
        documents, service_context=service_context
    )
    return index


def get_answer(q):
    base_knowledge = """ """
    text_list = [base_knowledge]
    index = knowledged_qa_demo(text_list)
    response = index.query(q)
    return response.response


def get_similar(q):
    from pilot.vector_store.extract_tovec import knownledge_tovec_st

    docsearch = knownledge_tovec_st("./datasets/plan.md")
    docs = docsearch.similarity_search_with_score(q, k=1)

    for doc in docs:
        dc, s = doc
        print(s)
        yield dc.page_content


if __name__ == "__main__":
    # agent_demo()

    with gr.Blocks() as demo:
        gr.Markdown("数据库智能助手")
        with gr.Tab("知识问答"):
            text_input = gr.TextArea()
            text_output = gr.TextArea()
            text_button = gr.Button()

        text_button.click(get_similar, inputs=text_input, outputs=text_output)

    demo.queue(concurrency_count=3).launch(server_name="0.0.0.0")
