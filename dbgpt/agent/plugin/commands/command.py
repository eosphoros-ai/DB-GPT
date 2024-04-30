"""Command module."""
import json
from typing import Any, Dict

from dbgpt._private.config import Config
from dbgpt.agent.plugin.generator import PluginPromptGenerator

from .exceptions import (
    CreateCommandException,
    ExecutionCommandException,
    NotCommandException,
)


def _resolve_pathlike_command_args(command_args):
    if "directory" in command_args and command_args["directory"] in {"", "/"}:
        # todo
        command_args["directory"] = ""
    else:
        for pathlike in ["filename", "directory", "clone_path"]:
            if pathlike in command_args:
                # todo
                command_args[pathlike] = ""
    return command_args


def execute_ai_response_json(
    prompt: PluginPromptGenerator,
    ai_response,
    user_input: str | None = None,
) -> str:
    """Execute the command from the AI response.

    Args:
        prompt(PluginPromptGenerator): The prompt generator
        ai_response: The response from the AI
        user_input(str): The user input

    Returns:
        str: The result of the command
    """
    from dbgpt.util.speech.say import say_text

    cfg = Config()

    command_name, arguments = get_command(ai_response)

    if cfg.speak_mode:
        say_text(f"I want to execute {command_name}")

    arguments = _resolve_pathlike_command_args(arguments)
    # Execute command
    if command_name is not None and command_name.lower().startswith("error"):
        result = f"Command {command_name} threw the following error: {arguments}"
    elif command_name == "human_feedback":
        result = f"Human feedback: {user_input}"
    else:
        for plugin in cfg.plugins:
            if not plugin.can_handle_pre_command():
                continue
            command_name, arguments = plugin.pre_command(command_name, arguments)
        command_result = execute_command(
            command_name,
            arguments,
            prompt,
        )
        result = f"{command_result}"
    return result


def execute_command(
    command_name: str,
    arguments: Dict[str, Any],
    plugin_generator: PluginPromptGenerator,
) -> Any:
    """Execute the command and return the result.

    Args:
        command_name (str): The name of the command to execute
        arguments (dict): The arguments for the command
        plugin_generator (PluginPromptGenerator): The plugin generator

    Returns:
        str: The result of the command

    Raises:
        NotCommandException: If the command is not found
        ExecutionCommandException: If an error occurs while executing the command
    """
    cmd = None
    if plugin_generator.command_registry:
        cmd = plugin_generator.command_registry.commands.get(command_name)

    # If the command is found, call it with the provided arguments
    if cmd:
        try:
            return cmd(**arguments)
        except Exception as e:
            raise CreateCommandException(f"Error: {str(e)}")
            # return f"Error: {str(e)}"
    # TODO: Change these to take in a file rather than pasted code, if
    # non-file is given, return instructions "Input should be a python
    # filepath, write your code to file and try again
    else:
        for command in plugin_generator.commands:
            if (
                command_name == command.label.lower()
                or command_name == command.name.lower()
            ):
                try:
                    # Delete non-defined parameters
                    diff_ags = list(
                        set(arguments.keys()).difference(set(command.args.keys()))
                    )
                    for arg_name in diff_ags:
                        del arguments[arg_name]
                    print(str(arguments))
                    func = command.function
                    if not func:
                        raise ExecutionCommandException(
                            f"Function not found for command: {command_name}"
                        )
                    return func(**arguments)
                except Exception as e:
                    raise ExecutionCommandException(f"Execution error: {str(e)}")
        raise NotCommandException("Invalid command: " + command_name)


def get_command(response_json: Dict):
    """Create a command from the response JSON.

    Parse the response and return the command name and arguments

    Args:
        response_json (json): The response from the AI

    Returns:
        tuple: The command name and arguments

    Raises:
        json.decoder.JSONDecodeError: If the response is not valid JSON

        Exception: If any other error occurs
    """
    try:
        if "command" not in response_json:
            return "Error:", "Missing 'command' object in JSON"

        if not isinstance(response_json, dict):
            return "Error:", f"'response_json' object is not dictionary {response_json}"

        command = response_json["command"]
        if not isinstance(command, dict):
            return "Error:", "'command' object is not a dictionary"

        if "name" not in command:
            return "Error:", "Missing 'name' field in 'command' object"

        command_name = command["name"]

        # Use an empty dictionary if 'args' field is not present in 'command' object
        arguments = command.get("args", {})

        return command_name, arguments
    except json.decoder.JSONDecodeError:
        return "Error:", "Invalid JSON"
    # All other errors, return "Error: + error message"
    except Exception as e:
        return "Error:", str(e)
