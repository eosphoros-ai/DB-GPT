#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from typing import Dict

from pilot.agent.json_fix_llm import fix_json_using_multiple_techniques
from pilot.commands.exception_not_commands import NotCommands
from pilot.configs.config import Config
from pilot.prompts.generator import PromptGenerator
from pilot.speech import say_text


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
    prompt: PromptGenerator,
    ai_response: str,
    user_input: str = None,
) -> str:
    """

    Args:
        command_registry:
        ai_response:
        prompt:

    Returns:

    """
    cfg = Config()
    try:
        assistant_reply_json = fix_json_using_multiple_techniques(ai_response)
    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        raise NotCommands("非可执行命令结构")
    command_name, arguments = get_command(assistant_reply_json)

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
    arguments,
    prompt: PromptGenerator,
):
    """Execute the command and return the result

    Args:
        command_name (str): The name of the command to execute
        arguments (dict): The arguments for the command

    Returns:
        str: The result of the command
    """

    cmd = prompt.command_registry.commands.get(command_name)

    # If the command is found, call it with the provided arguments
    if cmd:
        try:
            return cmd(**arguments)
        except Exception as e:
            return f"Error: {str(e)}"
    # TODO: Change these to take in a file rather than pasted code, if
    # non-file is given, return instructions "Input should be a python
    # filepath, write your code to file and try again
    else:
        for command in prompt.commands:
            if (
                command_name == command["label"].lower()
                or command_name == command["name"].lower()
            ):
                try:
                    # 删除非定义参数
                    diff_ags = list(
                        set(arguments.keys()).difference(set(command["args"].keys()))
                    )
                    for arg_name in diff_ags:
                        del arguments[arg_name]
                    print(str(arguments))
                    return command["function"](**arguments)
                except Exception as e:
                    return f"Error: {str(e)}"
        raise NotCommands("非可用命令" + command_name)


def get_command(response_json: Dict):
    """Parse the response and return the command name and arguments

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
