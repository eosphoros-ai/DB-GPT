from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.agents.planner_agent import PlannerAgent
from dbgpt.agent.agents.base_agent import PlanChat, PlanChatManager
from dbgpt.agent.agents.expand.code_assistant_agent import CodeAssistantAgent
from dbgpt.agent.agents.expand.sql_assistant_agent import SQLAssistantAgent

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.memory.gpts_memory import GptsMemory

async def test_plan_excute(message: str):
    context: AgentContext = AgentContext(conv_id="test456", gpts_name="测试助手2")
    context.db_name = 'dbgpt-test'
    context.llm_models = ["chatgpt_proxyllm", "tongyi_proxyllm"]
    context.resources['db'] = """
    	本地数据库. 可用表结构:{table_infos}
    """
    context.resources['internet'] = """
        互联网访问，用于搜索和信息收集，包括搜索引擎和指定地址网页浏览。
    """

    common_memory = GptsMemory()

    user_proxy = UserProxyAgent(
        name="Admin",
        memory=common_memory,
        describe="A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by this admin.",
        agent_context=context
    )

    developer = CodeAssistantAgent(
        name="CodeEngineer",
        memory=common_memory,
        agent_context=context,
        describe="""CodeEngineer.According to the current planning steps, write python/shell code to solve the problem, such as: data crawling, data sorting and conversion, etc. Wrap the code in a code block of the specified script type. Users cannot modify your code. So don't suggest incomplete code that needs to be modified by others.
          Don't include multiple code blocks in one response. Don't ask others to copy and paste the results.
        """    )

    data_analyst = SQLAssistantAgent(
        name="ChartEngineer",
        memory=common_memory,
        agent_context=context,
        describe="""ChartEngineer.You can analyze data with a known structure through SQL and generate a single analysis chart for a given target. Please note that you do not have the ability to obtain and process data and can only perform data analysis based on a given structure. If the task goal cannot or does not need to be solved by SQL analysis, please do not use
         """
    )



    groupchat = PlanChat(agents=[developer, data_analyst], messages=[], max_round=50)


    planner = PlannerAgent(
        describe="Generate a feasible action plan for user goals based on resources",
        agent_context=context,
        memory=common_memory,
        plan_chat=groupchat,
    )
    manager = PlanChatManager(plan_chat=groupchat, planner=planner, agent_context=context,   memory=common_memory,)

    await user_proxy.a_initiate_chat(
        recipient =manager,
        reviewer = user_proxy,
        message=message,
        memory=common_memory,
    )
    return context.conv_id

