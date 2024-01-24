# Local Data Analysis Agents

In this case, we will show you how to use  a data analysis agents, serving as a typical `GBI(Generative Business Intelligence)` application scenario. One can observe how Agents step by step analyze and solve problems through natural language interaction.

## How to use?
- **Data Preparation**
- **Add Data Source**
- **Insert Metadata**
- **Select Dialogue Scenario**
- **Select Agent**
- **Start Dialogue**


### Data Preparation
For data preparation, we can reuse the test data from the introductory tutorial; for detailed preparation steps, please refer to: [Data Preparation](/docs/application/started_tutorial/chat_dashboard#data-preparation).

### Add Data Source
Similarly, you may refer to the introductory tutorial on [how to add a data source](/docs/application/started_tutorial/chat_dashboard#add-data-source).


### Insert Metadata
Execute the following SQL statement to insert metadata.
```SQL
INSERT INTO dbgpt.gpts_instance
( gpts_name, gpts_describe, resource_db, resource_internet, resource_knowledge, gpts_agents, gpts_models, `language`, user_code, sys_code, created_at, updated_at, team_mode, is_sustainable)
VALUES('数据分析AI助手', '数据分析AI助手', '{"type": "\\u672c\\u5730\\u6570\\u636e\\u5e93", "name": "dbgpt_test", "introduce": ""}', '{"type": "\\u672c\\u5730\\u6570\\u636e\\u5e93", "name": "dbgpt_test", "introduce": ""}', '{"type": "\\u6587\\u6863\\u7a7a\\u95f4", "name": "TY", "introduce": " MYSQL\\u6570\\u636e\\u5e93\\u7684\\u5b98\\u65b9\\u64cd\\u4f5c\\u624b\\u518c"}', '["DataScientist", "Reporter"]', '{"DataScientist": ["vicuna-13b-v1.5", "tongyi_proxyllm", "chatgpt_proxyllm"], "Reporter": ["chatgpt_proxyllm", "tongyi_proxyllm","vicuna-13b-v1.5"], "default": ["chatgpt_proxyllm", "tongyi_proxyllm", "vicuna-13b-v1.5"]}', 'en', '', '', '2023-12-15 06:58:29', '2023-12-15 06:58:29', 'auto_plan', 0);
```

### Select Dialogue Scenario

<p align="left">
  <img src={'/img/agents/agent_scene.png'} width="720px" />
</p>

### Select Agent

<p align="left">
  <img src={'/img/agents/data_analysis_agent.png'} width="720px" />
</p>

### Start conversation
> 构建销售报表，分析用户的订单，从至少三个维度分析

<p align="left">
  <img src={'/img/agents/data_agents_charts.png'} width="720px" />
</p>

<p align="left">
  <img src={'/img/agents/data_agents_gif.gif'} width="720px" />
</p>
