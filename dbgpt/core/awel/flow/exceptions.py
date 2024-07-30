"""The exceptions for AWEL flow."""


class FlowException(Exception):
    """The base exception for AWEL flow."""

    def __init__(self, message: str, error_type: str = "Common Error"):
        """Create a new FlowException."""
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class FlowMetadataException(FlowException):
    """The base exception for AWEL flow metadata."""

    def __init__(self, message: str, error_type="build_metadata_error"):
        """Create a new FlowMetadataException."""
        super().__init__(message, error_type)


class FlowParameterMetadataException(FlowMetadataException):
    """The parameter metadata exception for AWEL flow metadata."""

    def __init__(self, message: str, error_type="build_parameter_metadata_error"):
        """Create a new FlowParameterMetadataException."""
        super().__init__(message, error_type)


class FlowClassMetadataException(FlowMetadataException):
    """The class metadata exception for AWEL flow metadata.

    Allways raise when load class from metadata failed.
    """

    def __init__(self, message: str, error_type="load_class_metadata_error"):
        """Create a new FlowClassMetadataException."""
        super().__init__(message, error_type)


class FlowDAGMetadataException(FlowMetadataException):
    """The exception for build DAG from metadata failed."""

    def __init__(self, message: str, error_type="build_dag_metadata_error"):
        """Create a new FlowDAGMetadataException."""
        super().__init__(message, error_type)


class FlowUIComponentException(FlowException):
    """The exception for UI parameter failed."""

    def __init__(
        self, message: str, component_name: str, error_type="build_ui_component_error"
    ):
        """Create a new FlowUIParameterException."""
        new_message = f"{component_name}: {message}"
        super().__init__(new_message, error_type)
