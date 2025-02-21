"""Code Assistant Agent."""

from typing import Optional, Tuple

from dbgpt.core import ModelMessageRoleType
from dbgpt.util.string_utils import str_to_bool

from ..core.agent import AgentMessage
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from .actions.code_action import CodeAction

CHECK_RESULT_SYSTEM_MESSAGE = (
    "You are an expert in analyzing the results of task execution. Your responsibility "
    "is to analyze the task goals and execution results provided by the user, and "
    "then make a judgment. You need to answer according to the following rules:\n"
    "          Rule 1: Determine whether the content of the focused execution results "
    "is related to the task target content and whether it can be used as the answer to "
    "the target question. For those who do not understand the content, as long as the "
    "execution result type is required, it can be judged as correct.\n"
    "          Rule 2: There is no need to pay attention to whether the boundaries, "
    "time range, and values of the answer content are correct.\n"
    "As long as the task goal and execution result meet the above rules, True will be "
    "returned; otherwise, False will be returned and the failure reason will be given."
    "\nFor example:\n"
    "        If it is determined to be successful, only true will be returned, "
    "such as: True.\n"
    "        If it is determined to be a failure, return false and the reason, "
    "such as: False. There are no numbers in the execution results that answer the "
    "computational goals of the mission.\n"
    "You can refer to the following examples:\n"
    "user: Please understand the following task objectives and results and give your "
    "judgment:\nTask goal: Calculate the result of 1 + 2 using Python code.\n"
    "Execution Result: 3\n"
    "assistant: True\n\n"
    "user: Please understand the following task objectives and results and give your "
    "judgment:\nTask goal: Calculate the result of 100 * 10 using Python code.\n"
    "Execution Result: 'you can get the result by multiplying 100 by 10'\n"
    "assistant: False. There are no numbers in the execution results that answer the "
    "computational goals of the mission.\n"
)


class CodeAssistantAgent(ConversableAgent):
    """Code Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Turing",
            category="agent",
            key="dbgpt_agent_expand_code_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "CodeEngineer",
            category="agent",
            key="dbgpt_agent_expand_code_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Solve tasks using your coding and language skills.\n"
            "In the following cases, suggest python code (in a python coding block) or "
            "shell script (in a sh coding block) for the user to execute.\n"
            "    1. When you need to collect info, use the code to output the info you "
            "need, for example, browse or search the web, download/read a file, print "
            "the content of a webpage or a file, get the current date/time, check the "
            "operating system. After sufficient info is printed and the task is ready "
            "to be solved based on your language skill, you can solve the task by "
            "yourself.\n"
            "    2. When you need to perform some task with code, use the code to "
            "perform the task and output the result. Finish the task smartly.",
            category="agent",
            key="dbgpt_agent_expand_code_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "The user cannot provide any other feedback or perform any other "
                "action beyond executing the code you suggest. The user can't modify "
                "your code. So do not suggest incomplete code which requires users to "
                "modify. Don't use a code block if it's not intended to be executed "
                "by the user.Don't ask users to copy and paste results. Instead, "
                "the 'Print' function must be used for output when relevant.",
                "When using code, you must indicate the script type in the code block. "
                "Please don't include multiple code blocks in one response.",
                "If you want the user to save the code in a file before executing it, "
                "put # filename: <filename> inside the code block as the first line.",
                "If you receive user input that indicates an error in the code "
                "execution, fix the error and output the complete code again. It is "
                "recommended to use the complete code rather than partial code or "
                "code changes. If the error cannot be fixed, or the task is not "
                "resolved even after the code executes successfully, analyze the "
                "problem, revisit your assumptions, gather additional information you "
                "need from historical conversation records, and consider trying a "
                "different approach.",
                "Unless necessary, give priority to solving problems with python "
                "code. If it involves downloading files or storing data locally, "
                "please use 'Print' to output the full file path of the stored data "
                "and a brief introduction to the data.",
                "The output content of the 'print' function will be passed to other "
                "LLM agents as dependent data. Please control the length of the "
                "output content of the 'print' function. The 'print' function only "
                "outputs part of the key data information that is relied on, "
                "and is as concise as possible.",
                "The code is executed without user participation. It is forbidden to "
                "use methods that will block the process or need to be shut down, "
                "such as the plt.show() method of matplotlib.pyplot as plt.",
                "It is prohibited to fabricate non-existent data to achieve goals.",
            ],
            category="agent",
            key="dbgpt_agent_expand_code_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Can independently write and execute python/shell code to solve various"
            " problems",
            category="agent",
            key="dbgpt_agent_expand_code_assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new CodeAssistantAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([CodeAction])

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify whether the current execution results meet the target expectations."""
        task_goal = message.current_goal
        action_report = message.action_report
        if not action_report:
            return False, "No execution solution results were checked"
        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content="Please understand the following task objectives and "
                    f"results and give your judgment:\n"
                    f"Task goal: {task_goal}\n"
                    f"Execution Result: {action_report.content}",
                )
            ],
            prompt=CHECK_RESULT_SYSTEM_MESSAGE,
        )
        success = str_to_bool(check_result)
        fail_reason = None
        if not success:
            fail_reason = (
                f"Your answer was successfully executed by the agent, but "
                f"the goal cannot be completed yet. Please regenerate based on the "
                f"failure reason:{check_result}"
            )
        return success, fail_reason
