"""A module for generating custom prompt strings."""
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .commands.command_manage import CommandRegistry


class CommandEntry(BaseModel):
    """CommandEntry class.

    A class for storing information about a command.
    """

    label: str = Field(
        ...,
        description="The label of the command.",
    )
    name: str = Field(
        ...,
        description="The name of the command.",
    )
    args: Dict[str, Any] = Field(
        default_factory=dict,
        description="A dictionary containing argument names and their values.",
    )
    function: Optional[Callable] = Field(
        None,
        description="A callable function to be called when the command is executed.",
    )


class PluginPromptGenerator:
    """PluginPromptGenerator class.

    A class for generating custom prompt strings based on constraints, commands,
        resources, and performance evaluations.
    """

    def __init__(self):
        """Create a new PromptGenerator object.

        Initialize the PromptGenerator object with empty lists of constraints,
        commands, resources, and performance evaluations.
        """
        from .commands.command_manage import CommandRegistry

        self._constraints: List[str] = []
        self._commands: List[CommandEntry] = []
        self._resources: List[str] = []
        self._performance_evaluation: List[str] = []
        self._command_registry: CommandRegistry = CommandRegistry()

    @property
    def constraints(self) -> List[str]:
        """Return the list of constraints."""
        return self._constraints

    @property
    def commands(self) -> List[CommandEntry]:
        """Return the list of commands."""
        return self._commands

    @property
    def resources(self) -> List[str]:
        """Return the list of resources."""
        return self._resources

    @property
    def performance_evaluation(self) -> List[str]:
        """Return the list of performance evaluations."""
        return self._performance_evaluation

    @property
    def command_registry(self) -> "CommandRegistry":
        """Return the command registry."""
        return self._command_registry

    def set_command_registry(self, command_registry: "CommandRegistry") -> None:
        """Set the command registry.

        Args:
            command_registry: CommandRegistry
        """
        self._command_registry = command_registry

    def add_constraint(self, constraint: str) -> None:
        """Add a constraint to the constraints list.

        Args:
            constraint (str): The constraint to be added.
        """
        self._constraints.append(constraint)

    def add_command(
        self,
        command_label: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
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

        command = CommandEntry(
            label=command_label,
            name=command_name,
            args=command_args,
            function=function,
        )
        self._commands.append(command)

    def _generate_command_string(self, command: CommandEntry) -> str:
        """
        Generate a formatted string representation of a command.

        Args:
            command (dict): A dictionary containing command information.

        Returns:
            str: The formatted command string.
        """
        args_string = ", ".join(
            f'"{key}": "{value}"' for key, value in command.args.items()
        )
        return f'"{command.name}": {command.label} , args: {args_string}'

    def add_resource(self, resource: str) -> None:
        """
        Add a resource to the resources list.

        Args:
            resource (str): The resource to be added.
        """
        self._resources.append(resource)

    def add_performance_evaluation(self, evaluation: str) -> None:
        """
        Add a performance evaluation item to the performance_evaluation list.

        Args:
            evaluation (str): The evaluation item to be added.
        """
        self._performance_evaluation.append(evaluation)

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
            if self._command_registry:
                command_strings += [
                    str(item)
                    for item in self._command_registry.commands.values()
                    if item.enabled
                ]
            # terminate command is added manually
            command_strings += [self._generate_command_string(item) for item in items]
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(command_strings))
        else:
            return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    def generate_commands_string(self) -> str:
        """Return a formatted string representation of the commands list."""
        return f"{self._generate_numbered_list(self._commands, item_type='command')}"
