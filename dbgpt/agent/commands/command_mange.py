import functools
import importlib
import inspect
import json
import logging
import xml.etree.ElementTree as ET

from dbgpt.util.json_utils import serialize
from datetime import datetime
from typing import Any, Callable, Optional, List
from dbgpt._private.pydantic import BaseModel
from dbgpt.agent.common.schema import Status
from dbgpt.agent.commands.command import execute_command
from dbgpt.util.string_utils import extract_content_open_ending, extract_content

# Unique identifier for auto-gpt commands
AUTO_GPT_COMMAND_IDENTIFIER = "auto_gpt_command"


class Command:
    """A class representing a command.

    Attributes:
        name (str): The name of the command.
        description (str): A brief description of what the command does.
        signature (str): The signature of the function that the command executes. Defaults to None.
    """

    def __init__(
        self,
        name: str,
        description: str,
        method: Callable[..., Any],
        signature: str = "",
        enabled: bool = True,
        disabled_reason: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.method = method
        self.signature = signature if signature else str(inspect.signature(self.method))
        self.enabled = enabled
        self.disabled_reason = disabled_reason

    def __call__(self, *args, **kwargs) -> Any:
        if not self.enabled:
            return f"Command '{self.name}' is disabled: {self.disabled_reason}"
        return self.method(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name}: {self.description}, args: {self.signature}"


class CommandRegistry:
    """
    The CommandRegistry class is a manager for a collection of Command objects.
    It allows the registration, modification, and retrieval of Command objects,
    as well as the scanning and loading of command plugins from a specified
    directory.
    """

    def __init__(self):
        self.commands = {}

    def _import_module(self, module_name: str) -> Any:
        return importlib.import_module(module_name)

    def _reload_module(self, module: Any) -> Any:
        return importlib.reload(module)

    def register(self, cmd: Command) -> None:
        self.commands[cmd.name] = cmd

    def unregister(self, command_name: str):
        if command_name in self.commands:
            del self.commands[command_name]
        else:
            raise KeyError(f"Command '{command_name}' not found in registry.")

    def reload_commands(self) -> None:
        """Reloads all loaded command plugins."""
        for cmd_name in self.commands:
            cmd = self.commands[cmd_name]
            module = self._import_module(cmd.__module__)
            reloaded_module = self._reload_module(module)
            if hasattr(reloaded_module, "register"):
                reloaded_module.register(self)

    def is_valid_command(self, name: str) -> bool:
        if name not in self.commands:
            return False
        else:
            return True

    def get_command(self, name: str) -> Callable[..., Any]:
        return self.commands[name]

    def call(self, command_name: str, **kwargs) -> Any:
        if command_name not in self.commands:
            raise KeyError(f"Command '{command_name}' not found in registry.")
        command = self.commands[command_name]
        return command(**kwargs)

    def command_prompt(self) -> str:
        """
        Returns a string representation of all registered `Command` objects for use in a prompt
        """
        commands_list = [
            f"{idx + 1}. {str(cmd)}" for idx, cmd in enumerate(self.commands.values())
        ]
        return "\n".join(commands_list)

    def import_commands(self, module_name: str) -> None:
        """
        Imports the specified Python module containing command plugins.

        This method imports the associated module and registers any functions or
        classes that are decorated with the `AUTO_GPT_COMMAND_IDENTIFIER` attribute
        as `Command` objects. The registered `Command` objects are then added to the
        `commands` dictionary of the `CommandRegistry` object.

        Args:
            module_name (str): The name of the module to import for command plugins.
        """

        module = importlib.import_module(module_name)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            # Register decorated functions
            if hasattr(attr, AUTO_GPT_COMMAND_IDENTIFIER) and getattr(
                attr, AUTO_GPT_COMMAND_IDENTIFIER
            ):
                self.register(attr.command)
            # Register command classes
            elif (
                inspect.isclass(attr) and issubclass(attr, Command) and attr != Command
            ):
                cmd_instance = attr()
                self.register(cmd_instance)


def command(
    name: str,
    description: str,
    signature: str = "",
    enabled: bool = True,
    disabled_reason: Optional[str] = None,
) -> Callable[..., Any]:
    """The command decorator is used to create Command objects from ordinary functions."""

    def decorator(func: Callable[..., Any]) -> Command:
        cmd = Command(
            name=name,
            description=description,
            method=func,
            signature=signature,
            enabled=enabled,
            disabled_reason=disabled_reason,
        )

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

        wrapper.command = cmd

        setattr(wrapper, AUTO_GPT_COMMAND_IDENTIFIER, True)

        return wrapper

    return decorator


class PluginStatus(BaseModel):
    name: str
    location: List[int]
    args: dict
    status: Status = Status.TODO.value
    logo_url: str = None
    api_result: str = None
    err_msg: str = None
    start_time = datetime.now().timestamp() * 1000
    end_time: int = None

    df: Any = None


class ApiCall:
    agent_prefix = "<api-call>"
    agent_end = "</api-call>"
    name_prefix = "<name>"
    name_end = "</name>"

    def __init__(
        self,
        plugin_generator: Any = None,
        display_registry: Any = None,
        backend_rendering: bool = False,
    ):
        # self.name: str = ""
        # self.status: Status = Status.TODO.value
        # self.logo_url: str = None
        # self.args = {}
        # self.api_result: str = None
        # self.err_msg: str = None

        self.plugin_status_map = {}

        self.plugin_generator = plugin_generator
        self.display_registry = display_registry
        self.start_time = datetime.now().timestamp() * 1000
        self.backend_rendering: bool = False

    def __repr__(self):
        return f"ApiCall(name={self.name}, status={self.status}, args={self.args})"

    def __is_need_wait_plugin_call(self, api_call_context):
        start_agent_count = api_call_context.count(self.agent_prefix)
        end_agent_count = api_call_context.count(self.agent_end)

        if start_agent_count > 0:
            return True
        else:
            # 末尾新出字符检测
            check_len = len(self.agent_prefix)
            last_text = api_call_context[-check_len:]
            for i in range(check_len):
                text_tmp = last_text[-i:]
                prefix_tmp = self.agent_prefix[:i]
                if text_tmp == prefix_tmp:
                    return True
                else:
                    i += 1
        return False

    def check_last_plugin_call_ready(self, all_context):
        start_agent_count = all_context.count(self.agent_prefix)
        end_agent_count = all_context.count(self.agent_end)

        if start_agent_count > 0 and start_agent_count == end_agent_count:
            return True
        return False

    def __deal_error_md_tags(self, all_context, api_context, include_end: bool = True):
        error_md_tags = [
            "```",
            "```python",
            "```xml",
            "```json",
            "```markdown",
            "```sql",
        ]
        if include_end == False:
            md_tag_end = ""
        else:
            md_tag_end = "```"
        for tag in error_md_tags:
            all_context = all_context.replace(
                tag + api_context + md_tag_end, api_context
            )
            all_context = all_context.replace(
                tag + "\n" + api_context + "\n" + md_tag_end, api_context
            )
            all_context = all_context.replace(
                tag + " " + api_context + " " + md_tag_end, api_context
            )
            all_context = all_context.replace(tag + api_context, api_context)
        return all_context

    def api_view_context(self, all_context: str, display_mode: bool = False):
        call_context_map = extract_content_open_ending(
            all_context, self.agent_prefix, self.agent_end, True
        )
        for api_index, api_context in call_context_map.items():
            api_status = self.plugin_status_map.get(api_context)
            if api_status is not None:
                if display_mode:
                    all_context = self.__deal_error_md_tags(all_context, api_context)
                    if Status.FAILED.value == api_status.status:
                        all_context = all_context.replace(
                            api_context,
                            f'\n<span style="color:red">Error:</span>{api_status.err_msg}\n'
                            + self.to_view_antv_vis(api_status),
                        )
                    else:
                        all_context = all_context.replace(
                            api_context, self.to_view_antv_vis(api_status)
                        )

                else:
                    all_context = self.__deal_error_md_tags(
                        all_context, api_context, False
                    )
                    all_context = all_context.replace(
                        api_context, self.to_view_text(api_status)
                    )

            else:
                # not ready api call view change
                now_time = datetime.now().timestamp() * 1000
                cost = (now_time - self.start_time) / 1000
                cost_str = "{:.2f}".format(cost)
                all_context = self.__deal_error_md_tags(all_context, api_context)

                all_context = all_context.replace(
                    api_context,
                    f'\n<span style="color:green">Waiting...{cost_str}S</span>\n',
                )

        return all_context

    def update_from_context(self, all_context):
        api_context_map = extract_content(
            all_context, self.agent_prefix, self.agent_end, True
        )
        for api_index, api_context in api_context_map.items():
            api_context = api_context.replace("\\n", "").replace("\n", "")
            api_call_element = ET.fromstring(api_context)
            api_name = api_call_element.find("name").text
            if api_name.find("[") >= 0 or api_name.find("]") >= 0:
                api_name = api_name.replace("[", "").replace("]", "")
            api_args = {}
            args_elements = api_call_element.find("args")
            for child_element in args_elements.iter():
                api_args[child_element.tag] = child_element.text

            api_status = self.plugin_status_map.get(api_context)
            if api_status is None:
                api_status = PluginStatus(
                    name=api_name, location=[api_index], args=api_args
                )
                self.plugin_status_map[api_context] = api_status
            else:
                api_status.location.append(api_index)

    def __to_view_param_str(self, api_status):
        param = {}
        if api_status.name:
            param["name"] = api_status.name
        param["status"] = api_status.status
        if api_status.logo_url:
            param["logo"] = api_status.logo_url

        if api_status.err_msg:
            param["err_msg"] = api_status.err_msg

        if api_status.api_result:
            param["result"] = api_status.api_result

        return json.dumps(param, default=serialize, ensure_ascii=False)

    def to_view_text(self, api_status: PluginStatus):
        api_call_element = ET.Element("dbgpt-view")
        api_call_element.text = self.__to_view_param_str(api_status)
        result = ET.tostring(api_call_element, encoding="utf-8")
        return result.decode("utf-8")

    def to_view_antv_vis(self, api_status: PluginStatus):
        if self.backend_rendering:
            html_table = api_status.df.to_html(
                index=False, escape=False, sparsify=False
            )
            table_str = "".join(html_table.split())
            table_str = table_str.replace("\n", " ")
            html = f""" \n<div><b>[SQL]{api_status.args["sql"]}</b></div><div class="w-full overflow-auto">{table_str}</div>\n """
            return html
        else:
            api_call_element = ET.Element("chart-view")
            api_call_element.attrib["content"] = self.__to_antv_vis_param(api_status)
            api_call_element.text = "\n"
            # api_call_element.set("content", self.__to_antv_vis_param(api_status))
            # api_call_element.text = self.__to_antv_vis_param(api_status)
            result = ET.tostring(api_call_element, encoding="utf-8")
            return result.decode("utf-8")

            # return f'<chart-view content="{self.__to_antv_vis_param(api_status)}">'

    def __to_antv_vis_param(self, api_status: PluginStatus):
        param = {}
        if api_status.name:
            param["type"] = api_status.name
        if api_status.args:
            param["sql"] = api_status.args["sql"]
        # if api_status.err_msg:
        #     param["err_msg"] = api_status.err_msg

        if api_status.api_result:
            param["data"] = api_status.api_result
        else:
            param["data"] = []
        return json.dumps(param, ensure_ascii=False)

    def run(self, llm_text):
        if self.__is_need_wait_plugin_call(llm_text):
            # wait api call generate complete
            if self.check_last_plugin_call_ready(llm_text):
                self.update_from_context(llm_text)
                for key, value in self.plugin_status_map.items():
                    if value.status == Status.TODO.value:
                        value.status = Status.RUNNING.value
                        logging.info(f"插件执行:{value.name},{value.args}")
                        try:
                            value.api_result = execute_command(
                                value.name, value.args, self.plugin_generator
                            )
                            value.status = Status.COMPLETED.value
                        except Exception as e:
                            value.status = Status.FAILED.value
                            value.err_msg = str(e)
                        value.end_time = datetime.now().timestamp() * 1000
        return self.api_view_context(llm_text)

    def run_display_sql(self, llm_text, sql_run_func):
        if self.__is_need_wait_plugin_call(llm_text):
            # wait api call generate complete
            if self.check_last_plugin_call_ready(llm_text):
                self.update_from_context(llm_text)
                for key, value in self.plugin_status_map.items():
                    if value.status == Status.TODO.value:
                        value.status = Status.RUNNING.value
                        logging.info(f"sql展示执行:{value.name},{value.args}")
                        try:
                            sql = value.args["sql"]
                            if sql:
                                param = {
                                    "df": sql_run_func(sql),
                                }
                                value.df = param["df"]
                                if self.display_registry.is_valid_command(value.name):
                                    value.api_result = self.display_registry.call(
                                        value.name, **param
                                    )
                                else:
                                    value.api_result = self.display_registry.call(
                                        "response_table", **param
                                    )

                            value.status = Status.COMPLETED.value
                        except Exception as e:
                            value.status = Status.FAILED.value
                            value.err_msg = str(e)
                        value.end_time = datetime.now().timestamp() * 1000
        return self.api_view_context(llm_text, True)

    def display_sql_llmvis(self, llm_text, sql_run_func):
        """
        Render charts using the Antv standard protocol
        Args:
            llm_text: LLM response text
            sql_run_func: sql run  function

        Returns:
           ChartView protocol text
        """
        try:
            if self.__is_need_wait_plugin_call(llm_text):
                # wait api call generate complete
                if self.check_last_plugin_call_ready(llm_text):
                    self.update_from_context(llm_text)
                    for key, value in self.plugin_status_map.items():
                        if value.status == Status.TODO.value:
                            value.status = Status.RUNNING.value
                            logging.info(f"sql展示执行:{value.name},{value.args}")
                            try:
                                sql = value.args["sql"]
                                if sql is not None and len(sql) > 0:
                                    data_df = sql_run_func(sql)
                                    value.df = data_df
                                    value.api_result = json.loads(
                                        data_df.to_json(
                                            orient="records",
                                            date_format="iso",
                                            date_unit="s",
                                        )
                                    )
                                    value.status = Status.COMPLETED.value
                                else:
                                    value.status = Status.FAILED.value
                                    value.err_msg = "No executable sql！"

                            except Exception as e:
                                value.status = Status.FAILED.value
                                value.err_msg = str(e)
                            value.end_time = datetime.now().timestamp() * 1000
        except Exception as e:
            logging.error("Api parsing exception", e)
            raise ValueError("Api parsing exception," + str(e))

        return self.api_view_context(llm_text, True)
