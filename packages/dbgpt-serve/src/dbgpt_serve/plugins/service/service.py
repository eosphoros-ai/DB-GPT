import logging
from pathlib import Path
from typing import List, Optional

from dbgpt.component import SystemApp
from dbgpt.storage.metadata import BaseDao
from dbgpt_serve.core import BaseService

from ..api.schemas import (
    SuiteEventResponse,
    SuiteRequest,
    SuiteResponse,
    SuiteSyncSummary,
)
from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..loader import read_skill_summaries, resolve_suites_dir, scan_suites
from ..models.models import SuiteDao, SuiteEntity, SuiteEventDao
from ..registry import SuiteRegistry

logger = logging.getLogger(__name__)


class Service(BaseService[SuiteEntity, SuiteRequest, SuiteResponse]):
    """Service for the plugins (expert suite) module."""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        config: ServeConfig,
        dao: Optional[SuiteDao] = None,
        event_dao: Optional[SuiteEventDao] = None,
    ):
        self._system_app = None
        self._serve_config: ServeConfig = config
        self._dao: Optional[SuiteDao] = dao
        self._event_dao: Optional[SuiteEventDao] = event_dao
        self._registry: Optional[SuiteRegistry] = None
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        super().init_app(system_app)
        self._dao = self._dao or SuiteDao(self._serve_config)
        self._event_dao = self._event_dao or SuiteEventDao(self._serve_config)
        self._registry = SuiteRegistry(self._dao, self._event_dao)
        self._system_app = system_app

    @property
    def dao(self) -> BaseDao[SuiteEntity, SuiteRequest, SuiteResponse]:
        return self._dao  # type: ignore[return-value]

    @property
    def config(self) -> ServeConfig:
        return self._serve_config

    @property
    def registry(self) -> SuiteRegistry:
        assert self._registry is not None, "service not initialized"
        return self._registry

    # ------------------------------------------------------------- startup sync
    def sync_official_on_start(self) -> SuiteSyncSummary:
        """Scan the suites dir and upsert official packages (fail-soft)."""
        root = resolve_suites_dir(self._serve_config.suites_dir)
        packages, warnings = scan_suites(root)
        summary = self.registry.sync_official(packages)
        summary.warnings.extend(warnings)
        logger.info(
            "suite sync: installed=%s upgraded=%s unchanged=%s disabled_missing=%s "
            "warnings=%d (root=%s)",
            summary.installed,
            summary.upgraded,
            summary.unchanged,
            summary.disabled_missing,
            len(summary.warnings),
            root,
        )
        return summary

    # ------------------------------------------------------------------- reads
    def list_suites(self, workspace_id: Optional[str] = None) -> List[SuiteResponse]:
        return self.registry.list_suites(workspace_id=workspace_id)

    def get(
        self, name: str, workspace_id: Optional[str] = None
    ) -> Optional[SuiteResponse]:
        response = self.registry.get(name, workspace_id=workspace_id)
        if response is not None:
            response.readme = self._read_readme(response.package_path)
            response.skill_details = read_skill_summaries(
                response.package_path,
                list((response.manifest_snapshot or {}).get("skills") or []),
            )
        return response

    @staticmethod
    def _read_readme(package_path: Optional[str]) -> Optional[str]:
        if not package_path:
            return None
        readme = Path(package_path) / "README.md"
        try:
            if readme.is_file():
                return readme.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001 - unreadable readme must not break detail
            logger.warning("suite readme unreadable: %s", readme)
        return None

    def list_events(self, name: str, limit: int = 100) -> List[SuiteEventResponse]:
        return self.registry.list_events(name, limit=limit)

    # ------------------------------------------------------------------ mutate
    def enable(
        self,
        name: str,
        workspace_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> SuiteResponse:
        return self.registry.set_enabled(
            name, True, workspace_id=workspace_id, user_name=user_name
        )

    def disable(
        self,
        name: str,
        workspace_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> SuiteResponse:
        return self.registry.set_enabled(
            name, False, workspace_id=workspace_id, user_name=user_name
        )

    def uninstall(self, name: str, user_name: Optional[str] = None) -> None:
        self.registry.uninstall(name, user_name=user_name)

    def install_package(self, pkg, user_name: Optional[str] = None) -> SuiteResponse:
        return self.registry.install_from_package(
            pkg, source="enterprise", user_name=user_name or "enterprise"
        )
