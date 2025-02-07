from .configs.agents import triage_agent
from .background import context_variables
from dbgpt.orhestrator.core import Matrix, Agent
from openai import AzureOpenAI
import os
from dotenv import dotenv_values

config = dotenv_values(r"orchestrator_test\orchestrator\.env")

print(config.get("AZURE_OPENAI_API_KEY"))
client = AzureOpenAI(
    azure_endpoint=config.get("AZURE_OPENAI_ENDPOINT"),
    api_version=config.get("AZURE_API_VERSION"),
    api_key=config.get("AZURE_OPENAI_API_KEY"),
)


client = Matrix(client=client)

# easier case
# agent = Agent(
#     name="Agent",
#     instructions="You are a helpful agent",
# )

# messages = [{"role": "user", "content": "Hi"}]

# response = client.run(agent=agent, messages=messages)

# print(response.messages)

# second test case

# english_agent = Agent(
#     name="English agent",
#     instructions="You only speck English.",
# )

# chinese_agent = Agent(
#     name="Chinese Agent",
#     instructions="You only speak Chinese.",
# )

# def transfer_to_chinese_agent():
#     """Transfer chinses speaking users immediately."""
#     return chinese_agent


# english_agent.functions.append(transfer_to_chinese_agent)
# messages = [{"role": "user", "content": "你好，最近有什么困惑吗？"}]

# response = client.run(agent=english_agent, messages=messages)

# print(response.messages[-1]["content"])
# translate agent running

messages = []
agent = triage_agent

messages.append({
    "role": "user",
    "content": "Hi, could u help me do a translation work?"
})

response = client.run(
    agent=agent,
    messages=messages,
    context_variables=context_variables or {},
    debug=True
)

def main(
        staring_agent, context_variables=None, stream=False, debug=False
) -> None:
    config = dotenv_values(r"orchestrator_test\orchestrator\.env")

    print(config.get("AZURE_OPENAI_API_KEY"))
    client = AzureOpenAI(
        azure_endpoint=config.get("AZURE_OPENAI_ENDPOINT"),
        api_version=config.get("AZURE_API_VERSION"),
        api_key=config.get("AZURE_OPENAI_API_KEY"),
    )

    client = Matrix(client=client)
    messages = []
    agent = staring_agent

    while True:
        user_input = input("\033[90mUser\033[0m: ")
        messages.append({"role": "user", "content": user_input})

        response = client.run(
            agent=agent,
            messages=messages,
            context_variables=context_variables or {},
            stream=stream,
            debug=debug,
        )

        messages.extend(response.messages)
        agent = response.agent
        
