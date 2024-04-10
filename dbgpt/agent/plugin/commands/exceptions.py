"""Exceptions for the commands plugin."""


class CommandException(Exception):
    """Common command error exception."""

    def __init__(self, message: str, error_type: str = "Common Error"):
        """Create a new CommandException instance."""
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class CreateCommandException(CommandException):
    """Create command error exception."""

    def __init__(self, message: str, error_type="Create Command Error"):
        """Create a new CreateCommandException instance."""
        super().__init__(message, error_type)


class NotCommandException(CommandException):
    """Command not found exception."""

    def __init__(self, message: str, error_type="Not Command Error"):
        """Create a new NotCommandException instance."""
        super().__init__(message, error_type)


class ExecutionCommandException(CommandException):
    """Command execution error exception."""

    def __init__(self, message: str, error_type="Execution Command Error"):
        """Create a new ExecutionCommandException instance."""
        super().__init__(message, error_type)
