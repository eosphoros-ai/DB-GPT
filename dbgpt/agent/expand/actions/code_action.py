"""Code Action Module."""

import logging
from typing import Optional, Union

from dbgpt.util.code_utils import UNKNOWN, execute_code, extract_code, infer_lang
from dbgpt.util.utils import colored
from dbgpt.vis.tags.vis_code import Vis, VisCode

from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource

logger = logging.getLogger(__name__)


class CodeAction(Action[None]):
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
            exitcode, logs = self.execute_code_blocks(code_blocks)
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
                    f"\n>>>>>>>> EXECUTING CODE BLOCK {i} "
                    f"(inferred language is {lang})...",
                    "red",
                ),
                flush=True,
            )
            if lang in ["bash", "shell", "sh"]:
                exitcode, logs, image = execute_code(
                    code, lang=lang, **self._code_execution_config
                )
            elif lang in ["python", "Python"]:
                if code.startswith("# filename: "):
                    filename = code[11 : code.find("\n")].strip()
                else:
                    filename = None
                exitcode, logs, image = execute_code(
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

    @property
    def use_docker(self) -> Union[bool, str, None]:
        """Whether to use docker to execute the code.

        Bool value of whether to use docker to execute the code,
        or str value of the docker image name to use, or None when code execution is
        disabled.
        """
        return (
            None
            if self._code_execution_config is False
            else self._code_execution_config.get("use_docker")
        )
