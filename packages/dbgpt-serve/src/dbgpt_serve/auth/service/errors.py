"""Stable business errors for authorization administration APIs."""


class ManagementError(Exception):
    """Base class for expected administration failures."""

    code = "MANAGEMENT_ERROR"


class ManagementNotFoundError(ManagementError):
    """Raised when a managed authorization object does not exist."""

    code = "NOT_FOUND"


class ManagementConflictError(ManagementError):
    """Raised when a requested state conflicts with current persisted state."""

    code = "CONFLICT"


class ManagementValidationError(ManagementError):
    """Raised when a cross-field business rule rejects a request."""

    code = "VALIDATION_ERROR"


class ImpactConfirmationRequiredError(ManagementConflictError):
    """Raised when a high-risk change lacks current impact confirmation."""

    code = "IMPACT_CONFIRMATION_REQUIRED"


class ImportSourceError(ManagementError):
    """Raised when the configured one-time import source cannot be read safely."""

    code = "IMPORT_SOURCE_UNAVAILABLE"
