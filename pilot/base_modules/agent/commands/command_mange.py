import functools
import importlib
import inspect
import json
import logging
import xml.etree.ElementTree as ET

from datetime import datetime
from typing import Any, Callable, Optional
from pilot.base_modules.agent.common.schema import Status, ApiTagType
from pilot.base_modules.agent.commands.command import execute_command
from pilot.base_modules.agent.commands.generator import PluginPromptGenerator
from pilot.common.string_utils import extract_content_include, extract_content_open_ending, extract_content, extract_content_include_open_ending

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


class ApiCall:
    agent_prefix = "<api-call>"
    agent_end = "</api-call>"
    name_prefix = "<name>"
    name_end = "</name>"

    def __init__(self, plugin_generator):
        self.name: str = ""
        self.status: Status = Status.TODO.value
        self.logo_url: str = None
        self.args = {}
        self.api_result: str = None
        self.err_msg: str = None
        self.plugin_generator = plugin_generator

    def __repr__(self):
        return f"ApiCall(name={self.name}, status={self.status}, args={self.args})"


    def __is_need_wait_plugin_call(self, api_call_context):

        if api_call_context.find(self.agent_prefix) >= 0:
            return True
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

    def __get_api_call_context(self, all_context):
      return  extract_content_include(all_context, self.agent_prefix, self.agent_end)

    def __check_plugin_call_ready(self, all_context):
        if all_context.find(self.agent_end) > 0:
            return True

    def api_view_context(self, all_context:str):
        if all_context.find(self.agent_prefix) >= 0:
            call_context = extract_content_open_ending(all_context, self.agent_prefix, self.agent_end)
            call_context_all = extract_content_include_open_ending(all_context, self.agent_prefix, self.agent_end)
            if len(call_context) > 0:
                name_context = extract_content(call_context, self.name_prefix, self.name_end)
                if len(name_context) > 0:
                    self.name = name_context
            return all_context.replace(call_context_all, self.to_view_text())
        else:
            return all_context

    def update_from_context(self, all_context):
        logging.info(f"from_context:{all_context}")
        api_context = extract_content_include(all_context, self.agent_prefix, self.agent_end)
        api_context = api_context.replace("\\n", "").replace("\n", "")

        api_call_element = ET.fromstring(api_context)
        self.name = api_call_element.find('name').text

        args_elements = api_call_element.find('args')
        for child_element in args_elements.iter():
            self.args[child_element.tag] = child_element.text

    def __to_view_param_str(self):
        param = {}
        if self.name:
            param['name'] = self.name
        param['status'] = self.status
        if self.logo_url:
            param['logo'] = self.logo_url

        if self.err_msg:
            param['err_msg'] = self.err_msg

        if self.api_result:
            param['result'] = self.api_result

        return json.dumps(param)

    def to_view_text(self):
        api_call_element = ET.Element('dbgpt-view')
        api_call_element.text = self.__to_view_param_str()
        result = ET.tostring(api_call_element, encoding="utf-8")
        return result.decode("utf-8")


    def run(self, llm_text):
        print(f"stream_plugin_call:{llm_text}")
        if self.__is_need_wait_plugin_call(llm_text):
            # wait api call generate complete
            if self.__check_plugin_call_ready(llm_text):
                self.update_from_context(llm_text)
                if self.status == Status.TODO.value:
                    self.status = Status.RUNNING.value
                    logging.info(f"插件执行:{self.name},{self.args}")
                    try:
                        self.api_result = execute_command(self.name, self.args, self.plugin_generator)
                        self.status = Status.COMPLETED.value
                    except Exception as e:
                        self.status = Status.FAILED.value
                        self.err_msg = str(e)
        return self.api_view_context(llm_text)