import autogen
from autogen import oai, AssistantAgent, UserProxyAgent, config_list_from_json
from openai.openai_object import OpenAIObject

config_list = [
    {
        "model": "gpt-3.5-turbo",
        "api_base": "http://43.156.9.162:3001/api/openai/v1",
        "api_type": "open_ai",
        "api_key": "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",
    }
]
llm_config = {
    "request_timeout": 600,
    "seed": 45,  # change the seed for different trials
    "config_list": config_list,
    "temperature": 0,
    "max_tokens": 3000,
}

# assistant = AssistantAgent("assistant", llm_config=llm_config)
# user_proxy = UserProxyAgent("user_proxy", code_execution_config={"work_dir": "coding"})
#

assistant = autogen.AssistantAgent(
    name="assistant",
    llm_config=llm_config,
    is_termination_msg=lambda x: True if "TERMINATE" in x.get("content") else False,
)

# 创建名为 user_proxy 的用户代理实例，这里定义为进行干预
user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=1,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={"work_dir": "web"},
    llm_config=llm_config,
    system_message="""Reply TERMINATE if the task has been solved at full satisfaction.
Otherwise, reply CONTINUE, or the reason why the task is not solved yet.""",
)

task1 = """今天是星期几？,还有几天周末？请告诉我答案。"""

if __name__ == "__main__":
    user_proxy.initiate_chat(assistant, message=task1)
    # user_proxy.initiate_chat(assistant, message="Plot a chart of NVDA and TESLA stock price change YTD.")

    # response: OpenAIObject = oai.Completion.create(
    #     config_list=[
    #         {
    #             "model": "gpt-3.5-turbo",
    #             "api_base": "http://43.156.9.162:3001/api/openai/v1",
    #             "api_type": "open_ai",
    #             "api_key": "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",
    #         }
    #     ],
    #     prompt="你好呀！",
    # )
    #
    # print(response)
    #
    # text = response.get("choices")[0].get("text")
    # print(text)
