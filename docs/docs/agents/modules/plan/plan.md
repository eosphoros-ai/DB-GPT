# Planning Introduction

> When faced with a complex task, humans tend to deconstruct it into simpler subtasks 
> and solve them individually. The planning module aims to empower the agents with such 
> human capability, which is expected to make the agent behave more reasonably, powerfully, and reliably.

In previous sections [Agents Planning](../../introduction/planning), we have seen the 
`AutoPlanChatManager` agent, and how it can be used to analyze the database with auto-planning.

## Planning With AWEL

Here we will introduce how to use the planning module in DB-GPT with `WrappedAWELLayoutManager`.
`WrappedAWELLayoutManager` will run the agents in a sequence, and the agents can be added to the manager by `hire` method.

Here is an example of how to use the `WrappedAWELLayoutManager`:

```python
import asyncio
import os

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    LLMConfig,
    UserProxyAgent,
    WrappedAWELLayoutManager,
)
from dbgpt.agent.expand.resources.search_tool import baidu_search
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.agent.expand.tool_assistant_agent import ToolAssistantAgent
from dbgpt.agent.resource import ToolPack
from dbgpt.model.proxy import OpenAILLMClient


async def main():
    llm_client = OpenAILLMClient(
        model_alias="gpt-4o",
        api_base=os.getenv("OPENAI_API_BASE"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    context: AgentContext = AgentContext(
        conv_id="test123", language="en", temperature=0.5, max_new_tokens=2048
    )
    agent_memory = AgentMemory()

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    tools = ToolPack([baidu_search])
    tool_engineer = (
        await ToolAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )
    summarizer = (
        await SummaryAssistantAgent()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )

    manager = (
        await WrappedAWELLayoutManager()
        .bind(context)
        .bind(agent_memory)
        .bind(LLMConfig(llm_client=llm_client))
        .build()
    )
    manager.hire([tool_engineer, summarizer])

    await user_proxy.initiate_chat(
        recipient=manager,
        reviewer=user_proxy,
        message="Query the weather in Beijing",
    )


if __name__ == "__main__":
    asyncio.run(main())

```

Run the above code, and you will see the agents running in sequence. And the output will be like this:

``````bash
--------------------------------------------------------------------------------
AWELBaseManager (to LuBan)-[]:

"Query the weather in Beijing"

--------------------------------------------------------------------------------
un_stream ai response: {
  "thought": "To find the current weather in Beijing, I will use the baidu_search API to search for the latest weather information.",
  "tool_name": "baidu_search",
  "args": {
    "query": "current weather in Beijing",
    "num_results": 8
  }
}

--------------------------------------------------------------------------------
LuBan (to Aristotle)-[gpt-4o]:

"{\n  \"thought\": \"To find the current weather in Beijing, I will use the baidu_search API to search for the latest weather information.\",\n  \"tool_name\": \"baidu_search\",\n  \"args\": {\n    \"query\": \"current weather in Beijing\",\n    \"num_results\": 8\n  }\n}"
>>>>>>>>LuBan Review info: 
Pass(None)
>>>>>>>>LuBan Action report: 
execution succeeded,
### [Weather for Beijing, Beijing Municipality, China](http://www.baidu.com/link?url=wpnRKEh7u3CA7C7n3f3wuit8nrIMJXReMRsPJ4gSiZGg_3sSCOuxi4rUSDGkxgG2CEAITa25NLfKcSZOK34kyq)
Location:Beijing Airport Current Time:25 Jun 2024, 16:31:38 Latest Report:25 Jun 2024, 08:30 Visibility:N/A Pressure:1009 mbar Humidity:32% Dew Point:10 °C Upcom...

### [Beijing, 11 10 天天气预报 - The Weather Channel | Weat...](http://www.baidu.com/link?url=BZa8Z5Ds-rPMRw0EZ0ly8tPzMbpYQ0CusdaFQ7RHkbHNOZMgf6wdK_j9vBISr2kLYE50_F5oxt9DHygAxaickcXVkgMi7e32C9vCZl_pQE0MpCt4sAc0PCjl8-NbThLAupds0gUYMbv2ejZjZN_ghQ6WW8EsJ_DzLSmD_eNfBdi)
准备好获悉最精确的Beijing, 11 10 天预报,包括最高温度、最低温度和降水几率 - 尽在 The Weather Channel 和 Weather.com

### [北京天气预报,历史气温,旅游指数,北京一周天气预报【携程...](http://www.baidu.com/link?url=BZa8Z5Ds-rPMRw0EZ0ly8wGkeEiW3HVrw0DkMBPB2xdL8dtIcOu3i6Gou-eLBrwmYuoxCdCOQSYuVdghSmPDKK)
查看城市旅游详情  22°C21℃/34℃  晴东北风 微风 风向情况:东北风 风力等级:微风 总降水量:0.0mm 相对湿度:98% 日出时间:4:46 日落时间:19:4736小时天气预报07:03发布 今天夜间21℃多云西...

### [【北京天气预报15天_北京天气预报15天查询】-中国天气网](http://www.baidu.com/link?url=giZXlwF5kTZfCHQNvHwkiVMJvxN6YGgBro45EL8_XgdzrAdxFhhg0zhG_qhYxdRUij1d1tl0NGqqRemZp7iT_a)
6月底前长江中下游及广西贵州等地将有强降雨天气2024-06-27 16:40 安徽今夜到后天强降雨连连 雨带明日北抬后天再度南落2024-06-27 16:20 风雨将至 北京天空出现大片乳状云 20...

### [【北京天气预报15天_北京天气预报15天查询】-中国天气网](http://www.baidu.com/link?url=SMy_6WtAuEY7oKXSbWW9obyaP_VAqzF7w550INK-8CnyaX4wrr1qlCBvhjCrYbaXeRpbT40-6pGXLuo_cQrTUq)
北方高温今明天短暂缓和 南方强降雨依然频繁2024-06-14 08:11 地质灾害风险预警:浙江福建广东广西等局地地质灾害气象风险高2024-06-14 17:32 渍涝风险气象预报:浙江福建广东...

### [【北京天气预报15天_北京天气预报15天查询】-中国天气网](http://www.baidu.com/link?url=wpnRKEh7u3CA7C7n3f3wun3KHDiGBTRXtwcgVgSV9e7Y7_Ui5d8PBraMakoZpeunwTcHgkwboa_9YZco1d3t6OpiMsXeEaim0ReUKbIZCP7Qa4c7ZZ1ZO1AtnILEXR1F)
6月底前长江中下游及广西贵州等地将有强降雨天气2024-06-27 16:40 安徽今夜到后天强降雨连连 雨带明日北抬后天再度南落2024-06-27 16:20 风雨将至 北京天空出现大片乳状云 20...

### [【北京天气预报15天_北京天气预报15天查询】-中国天气网](http://www.baidu.com/link?url=Qo1T3nlH9bZ57GJ7SSOVNwSZBKnCpwkkr95rpZY4XcK-W607jhYj10I6g_DwXWzlzLsK-siZKMZNN736q26OiJVP3u0aWyXLCRbRT4etDtu)
6月底前长江中下游及广西贵州等地将有强降雨天气2024-06-27 16:40 安徽今夜到后天强降雨连连 雨带明日北抬后天再度南落2024-06-27 16:20 风雨将至 北京天空出现大片乳状云 20...


--------------------------------------------------------------------------------
un_stream ai response: Beijing weather summary:
- Current temperature: 22°C
- Temperature range: 21°C to 34°C
- Conditions: Clear
- Wind: Northeast wind, light breeze
- Humidity: 98%
- No precipitation
- Sunrise: 4:46 AM
- Sunset: 7:47 PM

--------------------------------------------------------------------------------
AWELBaseManager (to User)-[]:

"Query the weather in Beijing"
>>>>>>>>AWELBaseManager Review info: 
Pass(None)
>>>>>>>>AWELBaseManager Action report: 
execution succeeded,
Beijing weather summary:
- Current temperature: 22°C
- Temperature range: 21°C to 34°C
- Conditions: Clear
- Wind: Northeast wind, light breeze
- Humidity: 98%
- No precipitation
- Sunrise: 4:46 AM
- Sunset: 7:47 PM

--------------------------------------------------------------------------------
``````