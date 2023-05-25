from typing import Any, Callable, Dict, List, Optional


class PromptGenerator:
    """
    generating custom prompt strings based on constraints；
    Compatible with AutoGpt Plugin;
    """

    def __init__(self) -> None:
        """
        Initialize the PromptGenerator object with empty lists of constraints,
            commands, resources, and performance evaluations.
        """
        self.constraints = []
        self.commands = []
        self.resources = []
        self.performance_evaluation = []
        self.goals = []
        self.command_registry = None
        self.name = "Bob"
        self.role = "AI"
        self.response_format = None

    def add_command(
        self,
        command_label: str,
        command_name: str,
        args=None,
        function: Optional[Callable] = None,
    ) -> None:
        """
        Add a command to the commands list with a label, name, and optional arguments.
        GB-GPT and Auto-GPT plugin registration command.
        Args:
            command_label (str): The label of the command.
            command_name (str): The name of the command.
            args (dict, optional): A dictionary containing argument names and their
              values. Defaults to None.
            function (callable, optional): A callable function to be called when
                the command is executed. Defaults to None.
        """
        if args is None:
            args = {}
        command_args = {arg_key: arg_value for arg_key, arg_value in args.items()}
        command = {
            "label": command_label,
            "name": command_name,
            "args": command_args,
            "function": function,
        }
        self.commands.append(command)
