# Crawl data analysis agents

In this case, the usage of an agent that automatcally writes programs to scrape internet data and perform analysis is demonstrated. One can observe through natural language interaction how the agent step by step completes the code writing process, and accomplishes the task handling. Unlike data analysis agents, the agent handles everything from code writing to data scraping and analysis autonomously, supporting direct data crawling from the internet for analysis.

## How to use?
Below are the steps for using the data scraping and analysis agent:

- **Write the agent**: in this case, we have already prepared the code writing assistant CodeAssistantAgent, with the source code located at dbgpt/agent/agents/expand/code_assistant_agent.py
- **Insert Metadata**
- **Select Dialogue Scenario**
- **Start Dialogue**

### Write the agent
In this case, the agent has already been programmed in the code, and the detailed code path is `dbgpt/agent/agents/expand/code_assistant_agent.py`. The specifics of the code are as follows. 

:::info note

At the same time, under the `dbgpt/agent/agents/expand` path, several other Agents have been implemented. Interested students can expand on their own.
:::

<p align="left">
  <img src={'/img/agents/code_agent.png'} width="720px" />
</p>

### Insert Metadata

The purpose of inserting metadata is to enable us to interact with the agent through the interactive interface.

```sql
INSERT INTO dbgpt.gpts_instance
(gpts_name, gpts_describe, resource_db, resource_internet, resource_knowledge, gpts_agents, gpts_models, `language`, user_code, sys_code, created_at, updated_at, team_mode, is_sustainable)
VALUES    (
          '互联网数据分析助手',
          '互联网数据分析助手',
          '',
          '{"type": "\\u4e92\\u8054\\u7f51\\u6570\\u636e", "name": "\\u6240\\u6709\\u6765\\u6e90\\u4e92\\u8054\\u7f51\\u7684\\u6570\\u636e", "introduce": "string"}',
          '{"type": "\\u6587\\u6863\\u7a7a\\u95f4", "name": "TY", "introduce": " MYSQL\\u6570\\u636e\\u5e93\\u7684\\u5b98\\u65b9\\u64cd\\u4f5c\\u624b\\u518c"}',
          '[ "CodeEngineer"]',
          '{"DataScientist": ["vicuna-13b-v1.5", "tongyi_proxyllm", "chatgpt_proxyllm"], "CodeEngineer": ["chatgpt_proxyllm", "tongyi_proxyllm", "vicuna-13b-v1.5"], "default": ["chatgpt_proxyllm", "tongyi_proxyllm", "vicuna-13b-v1.5"]}',
          'en',
          '',
          '',
          '2023-12-19 01:52:30',
          '2023-12-19 01:52:30',
          'auto_plan',
          0
          );
```

### Select Dialogue Scenario

We choose `Agent Chat` scene.

<p align="left">
  <img src={'/img/agents/agent_scene.png'} width="720px" />
</p>

After entering the scene, select the `Internet Data Analysis Assistant Agent` that we have just prepared, and then you can fulfill the requirements through a dialogue.

<p align="left">
  <img src={'/img/agents/crawl_agent.png'} width="720px" />
</p>


### Start Dialogue

> To obtain and analyze the issue data for the 'eosphoros-ai/DB-GPT' repository over the past week and create a Markdown table grouped by day and status.

<p align="left">
  <img src={'/img/agents/crawl_agent_issue.png'} width="720px" />
</p>
