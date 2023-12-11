import json

from pilot.dbgpts.agents.agent import Agent
from pilot.dbgpts.agents.conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from pilot.json_utils.utilities import find_json_objects
from pilot.common.schema import Status
from ..memory.gpts_memory import GptsMemory, GptsPlan, GptsMessage
from .planning_group_chat import PlanChat

class PlannerAgent(ConversableAgent):
    """ Planner agent, realizing task goal planning decomposition through LLM"""

    DEFAULT_SYSTEM_MESSAGE = """
    您是规划师，您需要理解用户问题，使用给出的资源，通过协调智能代理制定一个分步计划来完成用户的目标。
    
    资源：
        {all_resources}
    
    智能代理:
        {agents}
        
    *** 重要的提醒 ***
    - 将用户的目标分解为内容目标明确子任务，每个子任务都将是一个智能代理需要完成的独立目标
    - 使用提供的资源来协助生成计划步骤，根据用户目标的实际需要选择资源，不要使用不需要的资源
    - 每个步骤最好是使用一种资源完成一个子目标的任务，如果当前目标可以分解为同类型的多个子任务，可以生成相互不依赖的并行任务
    - 只使用提到的智能代理，并且可以只使用其中的部分，严格根据描述分配给合适的步骤，每个智能代理都可以重复使用，但尽量不要冗余
    - 尽量合并有顺序依赖的连续相同步骤,如果用户目标无拆分必要，可以生成内容为用户目标的单步任务

    请一步步思考，并以如下json格式返回你的行动计划内容:
    [{{
        "serial_number":"0",
        "agent": "适合完成当前步骤的智能代理，从提供的智能代理中选择",
        "content": "当前步骤的任务内容，确保可以被智能代理执行",
        "rely":"当前任务执行依赖的其他任务serial_number, 如:1,2,3,  无依赖为空"，
        "resource": "要使用的资源名称，如:本地数据库:xx, xx是名称"
    }}]
    确保回答的json可以被Python代码的json.loads函数加载解析.
    """

    REPAIR_SYSTEM_MESSAGE = """
     您是规划专家!现在你需要利用你的专业知识，仔细检查已生成的计划,进行重新评估和分析，确保计划的每个步骤都是清晰完整的，可以被智能代理理解的，解决当前计划中遇到的问题！并按要求返回新的计划内容。
    """

    def __init__(
            self,
            describe: Optional[str],
            memory: GptsMemory,
            plan_chat: PlanChat,
            is_termination_msg: Optional[Callable[[Dict], bool]] = None,
            max_consecutive_auto_reply: Optional[int] = None,
            human_input_mode: Optional[str] = "NEVER",
            agent_context: 'AgentContext' = None,
            **kwargs,
    ):
        super().__init__(
            name="Planner",
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )
        self.plan_chat = plan_chat
        ### register planning funtion
        self.register_reply(
            Agent,
            PlannerAgent._a_planning
        )


    async def a_receive(self, message: Union[Dict, str], sender: Agent, reviewer: "Agent",
                        request_reply: Optional[bool] = None, silent: Optional[bool] = False,   is_plan_goals: Optional[bool] = False):
        params = {
            "all_resources":  "\n".join([f"{i+1}. {value}" for i, value in enumerate(self.agent_context.resources.values())]),
            "agents":  "\n".join([f"- {item.name}:{item.describe}" for item in self.plan_chat.agents]),
        }

        ### If it is a message sent to yourself, go to repair sytem prompt
        if sender is self:
            self.update_system_message(self.REPAIR_SYSTEM_MESSAGE.format(**params))
        else:
            self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE.format(**params))
        return await super().a_receive(message, sender, reviewer, request_reply, silent)

    async def _a_planning(self,
                          message: Optional[str] = None,
                          sender: Optional[Agent] = None,
                          reviewer: "Agent" = None,
                          config: Optional[Any] = None,
                          ) -> Tuple[bool, Union[str, Dict, None]]:

        json_objects = find_json_objects(message)
        plan_objects = []
        fail_reason = "Please recheck your answer，no usable plans generated in correct format，"
        json_count = len(json_objects)
        rensponse_succ = True
        if json_count != 1:
            ### Answer failed, turn on automatic repair
            fail_reason += f"There are currently {json_count} json contents"
            rensponse_succ = False
        else:
            try:
                for item in json_objects[0]:
                    plan = GptsPlan(conv_id = self.agent_context.conv_id, sub_task_num = item.get('serial_number'), sub_task_content = item.get('content'))
                    plan.resource_name = item.get('resource')
                    plan.max_retry_times = self.agent_context.max_retry_round
                    plan.sub_task_agent = item.get('agent')
                    plan.rely = item.get("rely")
                    plan.agent_model = json.dumps(self.agent_context.llm_models)
                    plan.retry_times = 0
                    plan.status = Status.TODO.value
                    plan_objects.append(plan)
            except Exception as e:
                fail_reason += f"Return json structure error and cannot be converted to a usable plan，{str(e)}"
                rensponse_succ = False

        if rensponse_succ:
            if len(plan_objects) > 0:
                ### Delete the old plan every time before saving it
                self.memory.plans_memory.remove_by_conv_id(self.agent_context.conv_id)
                self.memory.plans_memory.batch_save(plan_objects)

            content = ".\n".join(
                ["{},{}".format(index + 1, item.get('content')) for index, item in enumerate(json_objects[0])])
        else:
            content = fail_reason
        return True, {"is_exe_success": rensponse_succ, "content": content}