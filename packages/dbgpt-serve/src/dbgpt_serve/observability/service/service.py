"""Observability service — holds the active :class:`ObservabilityProvider`.

The serve endpoints delegate to this service, which in turn delegates to the
provider. The provider is instantiated from the dotted-path ``provider_cls``
config (mirrors ``tracer_storage_cls``), so swapping backends is a config change.
"""

import logging
from typing import Optional

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.observability.base import ObservabilityProvider
from dbgpt.util.module_utils import import_from_checked_string

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER_CLS = (
    "dbgpt.observability.default_provider.DefaultObservabilityProvider"
)


class Service(BaseComponent):
    """Service proxying observability reads to the configured provider."""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, config: Optional[ServeConfig] = None):
        # BaseComponent.__init__ calls init_app(system_app) immediately, and our
        # init_app reads self._config / self._provider, so set them BEFORE super().
        self._system_app = system_app
        self._config: Optional[ServeConfig] = config
        self._provider: Optional[ObservabilityProvider] = None
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        self._system_app = system_app
        config = self._config
        if config is None:
            config = ServeConfig()
        provider_cls = config.provider_cls or DEFAULT_PROVIDER_CLS
        logger.info(f"Loading observability provider: {provider_cls}")
        cls = import_from_checked_string(provider_cls, ObservabilityProvider)
        try:
            self._provider = cls(sqlite_path=config.sqlite_path)
        except TypeError:
            # Provider does not accept sqlite_path (e.g. a future ZizkaDB impl).
            self._provider = cls()
        self._provider.init_app(system_app)

    @property
    def provider(self) -> ObservabilityProvider:
        if self._provider is None:
            raise RuntimeError("Observability provider not initialized")
        return self._provider
