"""dbgpt.agent.resource.connector — External connector primitives."""

from .catalog import ConnectorCatalog, ConnectorCatalogEntry
from .confirmation import (
    ConfirmationInterceptor,
    ConfirmationRegistry,
    PendingConfirmation,
)
from .credential import CredentialStore
from .manager import ConnectorManager, ConnectorStatus
from .scheduler import ConnectorScheduler
from .skill_integration import (
    check_skill_connector_availability,
    resolve_skill_connectors,
)

__all__ = [
    "ConnectorCatalog",
    "ConnectorCatalogEntry",
    "CredentialStore",
    "ConfirmationInterceptor",
    "ConfirmationRegistry",
    "PendingConfirmation",
    "ConnectorManager",
    "ConnectorStatus",
    "ConnectorScheduler",
    "resolve_skill_connectors",
    "check_skill_connector_availability",
]
