"""Exceptions for the tool."""


class ToolException(Exception):
    """Common tool error exception."""

    def __init__(self, message: str, error_type: str = "Common Error"):
        """Create a new ToolException instance."""
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class CreateToolException(ToolException):
    """Create tool error exception."""

    def __init__(self, message: str, error_type="Create Command Error"):
        """Create a new CreateToolException instance."""
        super().__init__(message, error_type)


class ToolNotFoundException(ToolException):
    """Tool not found exception."""

    def __init__(self, message: str, error_type="Not Command Error"):
        """Create a new ToolNotFoundException instance."""
        super().__init__(message, error_type)


class ToolExecutionException(ToolException):
    """Tool execution error exception."""

    def __init__(self, message: str, error_type="Execution Command Error"):
        """Create a new ToolExecutionException instance."""
        super().__init__(message, error_type)
