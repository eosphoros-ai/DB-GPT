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
        from ..creation import SuiteCreationStore

        drafts = SuiteCreationStore()
        packages = [
            pkg
            for pkg in packages
            if not drafts.has_installation_intent(pkg.name)
            or self.registry.get(pkg.name) is not None
        ]
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
            response.readme_locales = {
                locale: text
                for locale in ("en", "zh")
                if (text := self._read_readme(response.package_path, locale))
            }
            response.skill_details = read_skill_summaries(
                response.package_path,
                list((response.manifest_snapshot or {}).get("skills") or []),
            )
        return response

    @staticmethod
    def _read_readme(
        package_path: Optional[str], locale: Optional[str] = None
    ) -> Optional[str]:
        if not package_path:
            return None
        root = Path(package_path).resolve()
        readme = root / (f"README.{locale}.md" if locale else "README.md")
        try:
            if readme.resolve().is_relative_to(root) and readme.is_file():
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
        suite = self.get(name, workspace_id=workspace_id)
        if suite and (suite.manifest_snapshot or {}).get("required_resources"):
            from ..creation import SuiteCreationStore

            if not SuiteCreationStore().configuration(name).get("database_name"):
                raise ValueError("套件需要数据库配置，请从产物卡片选择数据库后启用")
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

    def install_generated_package(
        self, pkg, artifact_id: str, pending_configuration: bool
    ) -> SuiteResponse:
        """Commit generated registration and audit together, initially disabled
        when resources still need to be selected by the user."""
        import json
        from datetime import datetime

        from ..models.models import SuiteEventEntity

        status = "disabled" if pending_configuration else "enabled"
        entity = SuiteEntity(
            name=pkg.name,
            version=pkg.version,
            source="enterprise",
            display=pkg.manifest.get("display"),
            icon=pkg.manifest.get("icon"),
            scenario_id=pkg.manifest.get("scenario_id"),
            execution="react",
            status=status,
            workspace_id=None,
            package_path=pkg.path,
            package_digest=pkg.digest,
            manifest_snapshot=json.dumps(pkg.snapshot, ensure_ascii=False),
            use_count=0,
            user_name="suite-creator",
            enabled_at=datetime.utcnow() if status == "enabled" else None,
        )
        with self._dao.session() as session:
            session.add(entity)
            session.add(
                SuiteEventEntity(
                    suite_name=pkg.name,
                    event_type="install",
                    to_version=pkg.version,
                    user_name="suite-creator",
                    detail=json.dumps(
                        {
                            "artifact_id": artifact_id,
                            "digest": pkg.digest,
                            "pending_configuration": pending_configuration,
                        }
                    ),
                )
            )
            session.flush()
            session.expunge(entity)
        return self._dao.to_response(entity)
