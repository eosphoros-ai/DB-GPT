#!/usr/bin/env python3
# -*- coding:utf-8 -*-


from langchain.agents import (
    load_tools,
    initialize_agent,
    AgentType
)

from pilot.model.vicuna_llm import VicunaRequestLLM, VicunaEmbeddingLLM
llm = VicunaRequestLLM()

tools = load_tools(['python_repl'], llm=llm)
agent = initialize_agent(tools, llm, agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION, verbose=True)
agent.run(
    "Write a python script that prints 'Hello World!'"
)