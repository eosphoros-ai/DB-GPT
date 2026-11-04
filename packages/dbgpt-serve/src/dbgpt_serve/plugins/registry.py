"""Suite registry: install state + audit events.

Design invariants (scenario-suite-schema-design.md):
- the package on disk is the source of truth; the registry only records
  install state, version pin source and a rebuildable manifest snapshot;
- startup sync is idempotent (digest + version based);
- a package removed from disk degrades to ``disabled`` instead of erroring;
- every state transition writes one ``plugins_event`` row.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .api.schemas import SuiteEventResponse, SuiteResponse, SuiteSyncSummary
from .loader import SuitePackage
from .models.models import SuiteDao, SuiteEntity, SuiteEventDao

logger = logging.getLogger(__name__)

STATUS_INSTALLED = "installed"
STATUS_ENABLED = "enabled"
STATUS_DISABLED = "disabled"


class SuiteRegistry:
    """Registry facade over the two plugins tables."""

    def __init__(self, dao: SuiteDao, event_dao: SuiteEventDao):
        self._dao = dao
        self._event_dao = event_dao

    # ------------------------------------------------------------------ sync
    def sync_official(
        self, packages: List[SuitePackage], user_name: str = "system"
    ) -> SuiteSyncSummary:
        """Idempotent upsert of official packages discovered on disk."""
        summary = SuiteSyncSummary()
        seen = set()
        for pkg in packages:
            seen.add(pkg.name)
            existing = self._dao.get_by_name(pkg.name)
            if existing is None:
                self._dao.insert_official(
                    pkg, status=STATUS_ENABLED, user_name=user_name
                )
                self.record_event(
                    pkg.name,
                    "install",
                    to_version=pkg.version,
                    detail={"digest": pkg.digest, "skills": pkg.skills},
                    user_name=user_name,
                )
                summary.installed.append(pkg.name)
            elif (
                existing.version != pkg.version or existing.package_digest != pkg.digest
            ):
                from_version = existing.version
                self._dao.update_package(existing, pkg, user_name=user_name)
                self.record_event(
                    pkg.name,
                    "upgrade",
                    from_version=from_version,
                    to_version=pkg.version,
                    detail={"digest": pkg.digest},
                    user_name=user_name,
                )
                summary.upgraded.append(pkg.name)
            else:
                self._refresh_snapshot(existing, pkg)
                summary.unchanged.append(pkg.name)

        # Packages removed from disk: fail-soft disable, never raise.
        for row in self._dao.list_by_source("official"):
            if row.name in seen or row.status == STATUS_DISABLED:
                continue
            self._dao.set_status(row.name, STATUS_DISABLED, user_name=user_name)
            self.record_event(
                row.name,
                "disable",
                from_version=row.version,
                to_version=row.version,
                detail={"reason": "package_missing"},
                user_name=user_name,
            )
            summary.disabled_missing.append(row.name)
        return summary

    # ------------------------------------------------------------- runtime ops
    def _refresh_snapshot(self, existing: SuiteEntity, pkg: SuitePackage) -> None:
        """Rebuild derived metadata when the loader changes for the same package."""
        if self._dao.to_response(existing).manifest_snapshot != pkg.snapshot:
            self._dao.update_package(
                existing, pkg, user_name=existing.user_name or "system"
            )

    def set_enabled(
        self,
        name: str,
        enabled: bool,
        workspace_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> SuiteResponse:
        row = self._dao.get_by_name(name, workspace_id=workspace_id)
        if row is None:
            raise ValueError(f"suite not installed: {name}")
        status = STATUS_ENABLED if enabled else STATUS_DISABLED
        self._dao.set_status(
            name, status, workspace_id=workspace_id, user_name=user_name
        )
        self.record_event(
            name,
            "enable" if enabled else "disable",
            from_version=row.version,
            to_version=row.version,
            workspace_id=workspace_id,
            user_name=user_name,
        )
        updated = self._dao.get_by_name(name, workspace_id=workspace_id)
        return self._dao.to_response(updated)  # type: ignore[arg-type]

    def record_pin(
        self,
        conv_uid: str,
        name: str,
        version: str,
        user_name: Optional[str] = None,
    ) -> None:
        """Conversation created with a suite pin (ext_info.suite written by caller)."""
        self._dao.bump_use_count(name)
        self.record_event(
            name, "pin", to_version=version, conv_uid=conv_uid, user_name=user_name
        )

    def current_pin(self, conv_uid: str) -> Optional[tuple]:
        """Sticky conversation pin = latest pin/switch event for the conv."""
        if not conv_uid:
            return None
        rows = self._event_dao.list_by_conv(conv_uid)
        for row in reversed(rows):  # list_by_conv is asc; latest last
            if row.event_type in ("pin", "switch"):
                return (row.suite_name, row.to_version or "")
        return None

    def record_switch(
        self,
        conv_uid: str,
        from_suite: str,
        from_version: str,
        to_suite: str,
        to_version: str,
        reason: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> None:
        detail: Dict[str, Any] = {"from": f"{from_suite}@{from_version}"}
        if reason:
            detail["reason"] = reason
        self.record_event(
            to_suite,
            "switch",
            from_version=from_version,
            to_version=to_version,
            conv_uid=conv_uid,
            detail=detail,
            user_name=user_name,
        )

    def record_event(
        self,
        suite_name: str,
        event_type: str,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
        conv_uid: Optional[str] = None,
        workspace_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        user_name: Optional[str] = None,
    ) -> None:
        self._event_dao.add_event(
            suite_name=suite_name,
            event_type=event_type,
            from_version=from_version,
            to_version=to_version,
            conv_uid=conv_uid,
            workspace_id=workspace_id,
            detail=detail,
            user_name=user_name,
        )

    # ------------------------------------------------------------------ reads
    def install_from_package(
        self, pkg: SuitePackage, source: str = "enterprise", user_name: str = "system"
    ) -> SuiteResponse:
        """Register an uploaded (enterprise) package; upgrades when re-uploaded."""
        existing = self._dao.get_by_name(pkg.name)
        if existing is None:
            self._dao.insert_official(
                pkg, status=STATUS_ENABLED, user_name=user_name, source=source
            )
            self.record_event(
                pkg.name,
                "install",
                to_version=pkg.version,
                detail={"digest": pkg.digest, "source": source},
                user_name=user_name,
            )
        elif existing.version != pkg.version or existing.package_digest != pkg.digest:
            from_version = existing.version
            self._dao.update_package(existing, pkg, user_name=user_name)
            self.record_event(
                pkg.name,
                "upgrade",
                from_version=from_version,
                to_version=pkg.version,
                detail={"digest": pkg.digest, "source": source},
                user_name=user_name,
            )
        else:
            self._refresh_snapshot(existing, pkg)
        row = self._dao.get_by_name(pkg.name)
        return self._dao.to_response(row)  # type: ignore[arg-type]

    def uninstall(self, name: str, user_name: Optional[str] = None) -> None:
        """Remove the registry row (package files on disk are left untouched)."""
        row = self._dao.get_by_name(name)
        if row is None:
            raise ValueError(f"suite not installed: {name}")
        version = row.version
        self._dao.delete_by_id(row.id)  # type: ignore[arg-type]
        self.record_event(name, "uninstall", from_version=version, user_name=user_name)

    def list_suites(self, workspace_id: Optional[str] = None) -> List[SuiteResponse]:
        rows = self._dao.list_all(workspace_id=workspace_id)
        responses = [self._dao.to_response(r) for r in rows]
        responses.sort(key=lambda r: (r.status != STATUS_ENABLED, r.name))
        return responses

    def get(
        self, name: str, workspace_id: Optional[str] = None
    ) -> Optional[SuiteResponse]:
        row = self._dao.get_by_name(name, workspace_id=workspace_id)
        return self._dao.to_response(row) if row else None

    def list_events(self, name: str, limit: int = 100) -> List[SuiteEventResponse]:
        rows = self._event_dao.list_by_suite(name, limit=limit)
        return [self._event_dao.to_response(r) for r in rows]
