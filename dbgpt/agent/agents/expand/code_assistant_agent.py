import json
from typing import Callable, Dict, Literal, Optional, Union

from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.util.code_utils import UNKNOWN, execute_code, extract_code, infer_lang
from dbgpt.util.string_utils import str_to_bool
from dbgpt.util.utils import colored

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext
from ..base_agent import ConversableAgent


class CodeAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are a helpful AI assistant.
    Solve tasks using your coding and language skills.
    In the following cases, suggest python code (in a python coding block) or shell script (in a sh coding block) for the user to execute.
        1. When you need to collect info, use the code to output the info you need, for example, browse or search the web, download/read a file, print the content of a webpage or a file, get the current date/time, check the operating system. After sufficient info is printed and the task is ready to be solved based on your language skill, you can solve the task by yourself.
        2. When you need to perform some task with code, use the code to perform the task and output the result. Finish the task smartly.

    *** IMPORTANT REMINDER ***
    -  The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.Don't ask users to copy and paste results. Instead, the "Print" function must be used for output when relevant.
    - When using code, you must indicate the script type in the code block. Please don't include multiple code blocks in one response.
    - If you want the user to save the code in a file before executing it, put # filename: <filename> inside the code block as the first line.
    - If you receive user input that indicates an error in the code execution, fix the error and output the complete code again. It is recommended to use the complete code rather than partial code or code changes. If the error cannot be fixed, or the task is not resolved even after the code executes successfully, analyze the problem, revisit your assumptions, gather additional information you need from historical conversation records, and consider trying a different approach
    - Unless necessary, give priority to solving problems with python code. If it involves downloading files or storing data locally, please use "Print" to output the full file path of the stored data and a brief introduction to the data.
    - The output content of the "Print" function will be passed to other LLM agents. Please ensure that the information output by the "Print" function has been streamlined as much as possible and only retains key data information.
    - The code is executed without user participation. It is forbidden to use methods that will block the process or need to be shut down, such as the plt.show() method of matplotlib.pyplot as plt.
    """
    CHECK_RESULT_SYSTEM_MESSAGE = f"""
    You are an expert in analyzing the results of task execution.
    Your responsibility is to analyze the task goals and execution results provided by the user, and then make a judgment. You need to answer according to the following rules:
        Rule 1: Analysis and judgment only focus on whether the execution result is related to the task goal and whether it is answering the target question, but does not pay attention to whether the result content is reasonable or the correctness of the scope boundary of the answer content.
        Rule 2: If the target is a calculation type, there is no need to verify the correctness of the calculation of the values ​​in the execution result.
    As long as the execution result meets the task goal according to the above rules, True will be returned, otherwise False will be returned. Only returns True or False.
    """

    NAME = "CodeEngineer"
    DEFAULT_DESCRIBE = """According to the current planning steps, write python/shell code to solve the problem, such as: data crawling, data sorting and conversion, etc. Wrap the code in a code block of the specified script type. Users cannot modify your code. So don't suggest incomplete code that needs to be modified by others.
          Don't include multiple code blocks in one response. Don't ask others to copy and paste the results
    """

    def __init__(
        self,
        agent_context: AgentContext,
        memory: Optional[GptsMemory] = None,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        code_execution_config: Optional[Union[Dict, Literal[False]]] = None,
        **kwargs,
    ):
        """
        Args:
            name (str): agent name.
            system_message (str): system message for the ChatCompletion inference.
                Please override this attribute if you want to reprogram the agent.
            llm_config (dict): llm inference configuration.
                Please refer to [OpenAIWrapper.create](/docs/reference/oai/client#create)
                for available options.
            is_termination_msg (function): a function that takes a message in the form of a dictionary
                and returns a boolean value indicating if this received message is a termination message.
                The dict can contain the following keys: "content", "role", "name", "function_call".
            max_consecutive_auto_reply (int): the maximum number of consecutive auto replies.
                default to None (no limit provided, class attribute MAX_CONSECUTIVE_AUTO_REPLY will be used as the limit in this case).
                The limit only plays a role when human_input_mode is not "ALWAYS".
            **kwargs (dict): Please refer to other kwargs in
                [ConversableAgent](conversable_agent#__init__).
        """
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )
        self._code_execution_config: Union[Dict, Literal[False]] = (
            {} if code_execution_config is None else code_execution_config
        )
        ### register code funtion
        self.register_reply(Agent, CodeAssistantAgent.generate_code_execution_reply)

    def _vis_code_idea(self, code, exit_success, log, language):
        param = {}
        param["exit_success"] = exit_success
        param["language"] = language
        param["code"] = code
        param["log"] = log

        return f"```vis-code\n{json.dumps(param, ensure_ascii=False)}\n```"

    async def generate_code_execution_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply using code execution."""
        code_execution_config = (
            config if config is not None else self._code_execution_config
        )
        if code_execution_config is False:
            return False, None

        last_n_messages = code_execution_config.pop("last_n_messages", 1)

        # iterate through the last n messages reversly
        # if code blocks are found, execute the code blocks and return the output
        # if no code blocks are found, continue

        code_blocks = extract_code(message)

        if len(code_blocks) < 1:
            self.send(
                f"Failed to get valid answer,{message}", sender, None, silent=True
            )
        elif len(code_blocks) > 1 and code_blocks[0][0] == UNKNOWN:
            self.send(
                f"Failed to get valid answer,{message}", self, reviewer, silent=True
            )

        # found code blocks, execute code and push "last_n_messages" back
        exitcode, logs = self.execute_code_blocks(code_blocks)
        code_execution_config["last_n_messages"] = last_n_messages
        exit_success = True if exitcode == 0 else False
        if exit_success:
            return True, {
                "is_exe_success": exit_success,
                "content": f"{logs}",
                "view": self._vis_code_idea(
                    code_blocks, exit_success, logs, code_blocks[0][0]
                ),
            }
        else:
            return True, {
                "is_exe_success": exit_success,
                "content": f"exitcode: {exitcode} (execution failed)\n {logs}",
                "view": self._vis_code_idea(
                    code_blocks, exit_success, logs, code_blocks[0][0]
                ),
            }

    async def a_verify(self, message: Optional[Dict]):
        self.update_system_message(self.CHECK_RESULT_SYSTEM_MESSAGE)
        task_gogal = message.get("current_gogal", None)
        action_report = message.get("action_report", None)
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.a_reasoning_reply(
            [
                {
                    "role": ModelMessageRoleType.HUMAN,
                    "content": f"""Please understand the following task objectives and results and give your judgment:
                        Task Gogal: {task_gogal}
                        Execution Result: {task_result}
                    Only True or False is returned.
                    """,
                }
            ]
        )
        success = str_to_bool(check_result)
        fail_reason = None
        if not success:
            fail_reason = "The execution result of the code you wrote is judged as not answering the task question. Please re-understand and complete the task."
        return success, fail_reason

    @property
    def use_docker(self) -> Union[bool, str, None]:
        """Bool value of whether to use docker to execute the code,
        or str value of the docker image name to use, or None when code execution is disabled.
        """
        return (
            None
            if self._code_execution_config is False
            else self._code_execution_config.get("use_docker")
        )

    def run_code(self, code, **kwargs):
        """Run the code and return the result.

        Override this function to modify the way to run the code.
        Args:
            code (str): the code to be executed.
            **kwargs: other keyword arguments.

        Returns:
            A tuple of (exitcode, logs, image).
            exitcode (int): the exit code of the code execution.
            logs (str): the logs of the code execution.
            image (str or None): the docker image used for the code execution.
        """
        return execute_code(code, **kwargs)

    def execute_code_blocks(self, code_blocks):
        """Execute the code blocks and return the result."""
        logs_all = ""
        exitcode = -1
        for i, code_block in enumerate(code_blocks):
            lang, code = code_block
            if not lang:
                lang = infer_lang(code)
            print(
                colored(
                    f"\n>>>>>>>> EXECUTING CODE BLOCK {i} (inferred language is {lang})...",
                    "red",
                ),
                flush=True,
            )
            if lang in ["bash", "shell", "sh"]:
                exitcode, logs, image = self.run_code(
                    code, lang=lang, **self._code_execution_config
                )
            elif lang in ["python", "Python"]:
                if code.startswith("# filename: "):
                    filename = code[11 : code.find("\n")].strip()
                else:
                    filename = None
                exitcode, logs, image = self.run_code(
                    code,
                    lang="python",
                    filename=filename,
                    **self._code_execution_config,
                )
            else:
                # In case the language is not supported, we return an error message.
                exitcode, logs, image = (
                    1,
                    f"unknown language {lang}",
                    None,
                )
                # raise NotImplementedError
            if image is not None:
                self._code_execution_config["use_docker"] = image
            logs_all += "\n" + logs
            if exitcode != 0:
                return exitcode, logs_all
        return exitcode, logs_all
