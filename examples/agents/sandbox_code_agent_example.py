"""Run your code assistant agent in a sandbox environment.

This example demonstrates how to create a code assistant agent that can execute code
in a sandbox environment. The agent can execute Python and JavaScript code blocks
and provide the output to the user. The agent can also check the correctness of the
code execution results and provide feedback to the user.


You can limit the memory and file system resources available to the code execution
environment. The code execution environment is isolated from the host system,
preventing access to the internet and other external resources.
"""

import asyncio
import logging
from typing import Optional, Tuple

from dbgpt.agent import (
    Action,
    ActionOutput,
    AgentContext,
    AgentMemory,
    AgentMemoryFragment,
    AgentMessage,
    AgentResource,
    ConversableAgent,
    HybridMemory,
    LLMConfig,
    ProfileConfig,
    UserProxyAgent,
)
from dbgpt.agent.expand.code_assistant_agent import CHECK_RESULT_SYSTEM_MESSAGE
from dbgpt.core import ModelMessageRoleType
from dbgpt.util.code_utils import UNKNOWN, extract_code, infer_lang
from dbgpt.util.string_utils import str_to_bool
from dbgpt.util.utils import colored
from dbgpt.vis.tags.vis_code import Vis, VisCode

logger = logging.getLogger(__name__)


class SandboxCodeAction(Action[None]):
    """Code Action Module."""

    def __init__(self, **kwargs):
        """Code action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisCode()
        self._code_execution_config = {}

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        try:
            code_blocks = extract_code(ai_message)
            if len(code_blocks) < 1:
                logger.info(
                    f"No executable code found in answer,{ai_message}",
                )
                return ActionOutput(
                    is_exe_success=False, content="No executable code found in answer."
                )
            elif len(code_blocks) > 1 and code_blocks[0][0] == UNKNOWN:
                # found code blocks, execute code and push "last_n_messages" back
                logger.info(
                    f"Missing available code block type, unable to execute code,"
                    f"{ai_message}",
                )
                return ActionOutput(
                    is_exe_success=False,
                    content="Missing available code block type, "
                    "unable to execute code.",
                )
            exitcode, logs = await self.execute_code_blocks(code_blocks)
            exit_success = exitcode == 0

            content = (
                logs
                if exit_success
                else f"exitcode: {exitcode} (execution failed)\n {logs}"
            )

            param = {
                "exit_success": exit_success,
                "language": code_blocks[0][0],
                "code": code_blocks,
                "log": logs,
            }
            if not self.render_protocol:
                raise NotImplementedError("The render_protocol should be implemented.")
            view = await self.render_protocol.display(content=param)
            return ActionOutput(
                is_exe_success=exit_success,
                content=content,
                view=view,
                thoughts=ai_message,
                observations=content,
            )
        except Exception as e:
            logger.exception("Code Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content="Code execution exception，" + str(e)
            )

    async def execute_code_blocks(self, code_blocks):
        """Execute the code blocks and return the result."""
        from lyric import (
            PyTaskFilePerms,
            PyTaskFsConfig,
            PyTaskMemoryConfig,
            PyTaskResourceConfig,
        )

        from dbgpt.util.code.server import get_code_server

        fs = PyTaskFsConfig(
            preopens=[
                # Mount the /tmp directory to the /tmp directory in the sandbox
                # Directory permissions are set to 3 (read and write)
                # File permissions are set to 3 (read and write)
                ("/tmp", "/tmp", 3, 3),
                # Mount the current directory to the /home directory in the sandbox
                # Directory and file permissions are set to 1 (read)
                (".", "/home", 1, 1),
            ]
        )
        memory = PyTaskMemoryConfig(memory_limit=50 * 1024 * 1024)  # 50MB in bytes
        resources = PyTaskResourceConfig(
            fs=fs,
            memory=memory,
            env_vars=[
                ("TEST_ENV", "hello, im an env var"),
                ("TEST_ENV2", "hello, im another env var"),
            ],
        )

        code_server = await get_code_server()
        logs_all = ""
        exitcode = -1
        for i, code_block in enumerate(code_blocks):
            lang, code = code_block
            if not lang:
                lang = infer_lang(code)
            print(
                colored(
                    f"\n>>>>>>>> EXECUTING CODE BLOCK {i} "
                    f"(inferred language is {lang})...",
                    "red",
                ),
                flush=True,
            )
            if lang in ["python", "Python"]:
                result = await code_server.exec(code, "python", resources=resources)
                exitcode = result.exit_code
                logs = result.logs
            elif lang in ["javascript", "JavaScript"]:
                result = await code_server.exec(code, "javascript", resources=resources)
                exitcode = result.exit_code
                logs = result.logs
            else:
                # In case the language is not supported, we return an error message.
                exitcode, logs = (
                    1,
                    f"unknown language {lang}",
                )

            logs_all += "\n" + logs
            if exitcode != 0:
                return exitcode, logs_all
        return exitcode, logs_all


class SandboxCodeAssistantAgent(ConversableAgent):
    """Code Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name="Turing",
        role="CodeEngineer",
        goal=(
            "Solve tasks using your coding and language skills.\n"
            "In the following cases, suggest python code (in a python coding block) or "
            "javascript for the user to execute.\n"
            "    1. When you need to collect info, use the code to output the info you "
            "need, for example, get the current date/time, check the "
            "operating system. After sufficient info is printed and the task is ready "
            "to be solved based on your language skill, you can solve the task by "
            "yourself.\n"
            "    2. When you need to perform some task with code, use the code to "
            "perform the task and output the result. Finish the task smartly."
        ),
        constraints=[
            "The user cannot provide any other feedback or perform any other "
            "action beyond executing the code you suggest. The user can't modify "
            "your code. So do not suggest incomplete code which requires users to "
            "modify. Don't use a code block if it's not intended to be executed "
            "by the user.Don't ask users to copy and paste results. Instead, "
            "the 'Print' function must be used for output when relevant.",
            "When using code, you must indicate the script type in the code block. "
            "Please don't include multiple code blocks in one response.",
            "If you receive user input that indicates an error in the code "
            "execution, fix the error and output the complete code again. It is "
            "recommended to use the complete code rather than partial code or "
            "code changes. If the error cannot be fixed, or the task is not "
            "resolved even after the code executes successfully, analyze the "
            "problem, revisit your assumptions, gather additional information you "
            "need from historical conversation records, and consider trying a "
            "different approach.",
            "Unless necessary, give priority to solving problems with python " "code.",
            "The output content of the 'print' function will be passed to other "
            "LLM agents as dependent data. Please control the length of the "
            "output content of the 'print' function. The 'print' function only "
            "outputs part of the key data information that is relied on, "
            "and is as concise as possible.",
            "Your code will by run in a sandbox environment(supporting python and "
            "javascript), which means you can't access the internet or use any "
            "libraries that are not in standard library.",
            "It is prohibited to fabricate non-existent data to achieve goals.",
        ],
        desc=(
            "Can independently write and execute python/shell code to solve various"
            " problems"
        ),
    )

    def __init__(self, **kwargs):
        """Create a new CodeAssistantAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([SandboxCodeAction])

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


async def main():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-4o-mini")
    context: AgentContext = AgentContext(conv_id="test123")
    agent_memory = AgentMemory(HybridMemory[AgentMemoryFragment].from_chroma())
    agent_memory.gpts_memory.init("test123")

    coder = (
        await SandboxCodeAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(context).bind(agent_memory).build()

    # First case: The user asks the agent to calculate 321 * 123
    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="计算下321 * 123等于多少",
    )

    await user_proxy.initiate_chat(
        recipient=coder,
        reviewer=user_proxy,
        message="Calculate 100 * 99, must use javascript code block",
    )


if __name__ == "__main__":
    asyncio.run(main())
