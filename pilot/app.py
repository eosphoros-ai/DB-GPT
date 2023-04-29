#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import streamlit as st
from langchain.agents import (
    load_tools,
    initialize_agent,
    AgentType
)
from pilot.model.vicuna_llm import VicunaRequestLLM, VicunaEmbeddingLLM
from llama_index import LLMPredictor, LangchainEmbedding, ServiceContext
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from llama_index import Document, GPTSimpleVectorIndex

def agent_demo():
    llm = VicunaRequestLLM()

    tools = load_tools(['python_repl'], llm=llm)
    agent = initialize_agent(tools, llm, agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
    agent.run(
        "Write a SQL script that Query 'select count(1)!'"
    )

def knowledged_qa_demo(text_list):
    llm_predictor = LLMPredictor(llm=VicunaRequestLLM)
    hfemb = VicunaEmbeddingLLM()
    embed_model = LangchainEmbedding(hfemb)
    documents = [Document(t) for t in text_list]

    service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor, embed_model=embed_model)
    index = GPTSimpleVectorIndex.from_documents(documents, service_context=service_context) 
    return index


if __name__ == "__main__":
    # agent_demo()

    test1 = """ 这是一段测试文字  """
    text_list = [test1]
    index = knowledged_qa_demo(text_list)

    st.title("智能助手")
    query = st.text_input("请提问.")
    
    if st.button("提交"):
        response = index.query(query)
        print(query, response.response)
        st.write(response.response)