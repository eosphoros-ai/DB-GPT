"""Configuration for the observability serve module."""

from dataclasses import dataclass, field
from typing import Optional

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "observability"
SERVE_APP_NAME = "dbgpt_serve_observability"
SERVE_APP_NAME_HUMP = "dbgpt_serve_Observability"
SERVE_CONFIG_KEY_PREFIX = "dbgpt.serve.observability."
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"
SERVER_APP_TABLE_NAME = "dbgpt_serve_observability"


@auto_register_resource(
    label=_("Observability Serve Configurations"),
    category=ResourceCategory.COMMON,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Configuration for the observability serve module."),
    show_in_ui=False,
)
@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the observability serve module.

    The serve is a pure proxy to an :class:`ObservabilityProvider`; the provider
    implementation is selected via ``provider_cls`` (dotted path, mirroring
    ``tracer_storage_cls``). The default SQLite provider needs no external deps.
    """

    __type__ = APP_NAME

    provider_cls: Optional[str] = field(
        default=("dbgpt.observability.default_provider.DefaultObservabilityProvider"),
        metadata={
            "help": _(
                "Dotted-path class of the ObservabilityProvider implementation "
                "(default SQLite; set to the ZizkaDB provider for causal/drift/memory)"
            )
        },
    )
    sqlite_path: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "SQLite file path for the default provider "
                "(default logs/observability.db)"
            )
        },
    )
