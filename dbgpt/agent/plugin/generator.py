"""A module for generating custom prompt strings."""
from typing import Any, Callable, Dict, List, Optional


class PluginPromptGenerator:
    """PluginPromptGenerator class.

    A class for generating custom prompt strings based on constraints, commands,
        resources, and performance evaluations.
    """

    def __init__(self) -> None:
        """Create a new PromptGenerator object.

        Initialize the PromptGenerator object with empty lists of constraints,
        commands, resources, and performance evaluations.
        """
        from .commands.command_manage import CommandRegistry

        self.constraints: List[str] = []
        self.commands: List[Dict[str, Any]] = []
        self.resources: List[str] = []
        self.performance_evaluation: List[str] = []
        self.command_registry: CommandRegistry = CommandRegistry()

    def add_constraint(self, constraint: str) -> None:
        """Add a constraint to the constraints list.

        Args:
            constraint (str): The constraint to be added.
        """
        self.constraints.append(constraint)

    def add_command(
        self,
        command_label: str,
        command_name: str,
        args=None,
        function: Optional[Callable] = None,
    ) -> None:
        """Add a command to the commands.

        Add a command to the commands list with a label, name, and optional arguments.

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

    def _generate_command_string(self, command: Dict[str, Any]) -> str:
        """
        Generate a formatted string representation of a command.

        Args:
            command (dict): A dictionary containing command information.

        Returns:
            str: The formatted command string.
        """
        args_string = ", ".join(
            f'"{key}": "{value}"' for key, value in command["args"].items()
        )
        return f'"{command["name"]}": {command["label"]} , args: {args_string}'

    def add_resource(self, resource: str) -> None:
        """
        Add a resource to the resources list.

        Args:
            resource (str): The resource to be added.
        """
        self.resources.append(resource)

    def add_performance_evaluation(self, evaluation: str) -> None:
        """
        Add a performance evaluation item to the performance_evaluation list.

        Args:
            evaluation (str): The evaluation item to be added.
        """
        self.performance_evaluation.append(evaluation)

    def _generate_numbered_list(self, items: List[Any], item_type="list") -> str:
        """
        Generate a numbered list from given items based on the item_type.

        Args:
            items (list): A list of items to be numbered.
            item_type (str, optional): The type of items in the list.
                Defaults to 'list'.

        Returns:
            str: The formatted numbered list.
        """
        if item_type == "command":
            command_strings = []
            if self.command_registry:
                command_strings += [
                    str(item)
                    for item in self.command_registry.commands.values()
                    if item.enabled
                ]
            # terminate command is added manually
            command_strings += [self._generate_command_string(item) for item in items]
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(command_strings))
        else:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    def generate_commands_string(self) -> str:
        """Return a formatted string representation of the commands list."""
        return f"{self._generate_numbered_list(self.commands, item_type='command')}"
