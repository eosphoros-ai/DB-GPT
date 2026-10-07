"""Selection-aware Dashboard comments and preview-before-apply Agent changes."""

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .collaboration import (
    DashboardCollaborationService,
    DashboardPatchError,
    apply_dashboard_patch,
)
from .models import (
    DashboardAnnotationEntity,
    DashboardConflictError,
    DashboardNotFoundError,
)
from .schemas import (
    DashboardAction,
    DashboardAnnotationApplyRequest,
    DashboardAnnotationApplyResponse,
    DashboardAnnotationCreateRequest,
    DashboardAnnotationIntent,
    DashboardAnnotationRecord,
    DashboardAnnotationStatus,
    DashboardChangeProposal,
    DashboardChangeProposalRequest,
    DashboardOperationRequest,
    DashboardPatchOperation,
    DashboardSchemaV1,
    DashboardSelectionKind,
    DashboardStablePatchOperation,
    model_dump_compat,
    model_validate_compat,
)
from .service import (
    DashboardSchemaValidationError,
    DashboardService,
    _json_dumps,
)

MAX_ANNOTATION_TARGET_BYTES = 16 * 1024
_FILTER_BINDING_INTENT = re.compile(
    r"(影响组件|组件范围|绑定|SQL\s*参数|bind(?:ing)?|parameter\s+mapping)",
    re.IGNORECASE,
)
_NAMED_SQL_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


def _filter_binding_contract(
    schema: DashboardSchemaV1, filter_id: str
) -> Dict[str, Any]:
    contract: Dict[str, Any] = {}
    for widget in schema.widgets:
        binding = widget.query.filter_parameters.get(filter_id)
        if binding is not None:
            contract[f"widget:{widget.id}"] = (
                binding if isinstance(binding, str) else model_dump_compat(binding)
            )
        if widget.query.federation is None:
            continue
        for source in widget.query.federation.sources:
            binding = source.filter_parameters.get(filter_id)
            if binding is not None:
                contract[f"widget:{widget.id}:source:{source.alias}"] = (
                    binding if isinstance(binding, str) else model_dump_compat(binding)
                )
    return contract


def _validate_requested_filter_binding_change(
    prompt: str,
    target_payload: Dict[str, Any],
    before: DashboardSchemaV1,
    after: DashboardSchemaV1,
) -> None:
    """Reject a filter-binding proposal that only changes visible metadata."""

    if target_payload.get("kind") != DashboardSelectionKind.FILTER.value:
        return
    if not _FILTER_BINDING_INTENT.search(prompt or ""):
        return
    filter_id = str(target_payload.get("filter_id") or "")
    if not filter_id:
        raise DashboardPatchError("Filter binding proposals require a filter id.")
    previous = _filter_binding_contract(before, filter_id)
    proposed = _filter_binding_contract(after, filter_id)
    if proposed == previous:
        raise DashboardPatchError(
            f"The proposal requested component binding for filter '{filter_id}' "
            "but did not modify any widget filter_parameters mapping."
        )
    if not proposed:
        raise DashboardPatchError(
            f"Filter '{filter_id}' must be bound to at least one component query."
        )

    for widget in after.widgets:
        queries = [("query", widget.query.sql, widget.query.filter_parameters)]
        if widget.query.federation is not None:
            queries.extend(
                (
                    f"source '{source.alias}'",
                    source.sql,
                    source.filter_parameters,
                )
                for source in widget.query.federation.sources
            )
        for label, sql, mappings in queries:
            binding = mappings.get(filter_id)
            if binding is None:
                continue
            names = [binding] if isinstance(binding, str) else binding.parameter_names()
            sql_names = set(_NAMED_SQL_PARAMETER.findall(sql or ""))
            missing = [name for name in names if name not in sql_names]
            if missing:
                raise DashboardPatchError(
                    f"Filter '{filter_id}' mapping for widget '{widget.id}' {label} "
                    "does not exist in SQL: "
                    + ", ".join(f":{name}" for name in missing)
                    + "."
                )


def _decode_pointer(path: str) -> List[str]:
    if not path.startswith("/") or path == "/":
        raise DashboardPatchError("Stable patch paths must address a schema field.")
    decoded: List[str] = []
    for raw in path[1:].split("/"):
        value = ""
        index = 0
        while index < len(raw):
            if raw[index] != "~":
                value += raw[index]
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise DashboardPatchError(
                    "Stable patch path contains invalid JSON Pointer escaping."
                )
            value += "~" if raw[index + 1] == "0" else "/"
            index += 2
        decoded.append(value)
    return decoded


def _encode_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _find_id(items: List[Dict[str, Any]], item_id: str, label: str) -> int:
    for index, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("id")) == item_id:
            return index
    raise DashboardPatchError(f"{label} '{item_id}' no longer exists.")


def _find_layout(items: List[Dict[str, Any]], widget_id: str) -> int:
    for index, item in enumerate(items):
        if isinstance(item, dict) and str(item.get("widget_id")) == widget_id:
            return index
    raise DashboardPatchError(f"Layout for widget '{widget_id}' no longer exists.")


def resolve_stable_patch_operations(
    schema: DashboardSchemaV1,
    operations: List[DashboardStablePatchOperation],
) -> List[DashboardPatchOperation]:
    """Resolve each stable id against the preceding operations' preview state."""

    payload = model_dump_compat(schema)
    resolved: List[DashboardPatchOperation] = []
    for operation in operations:
        parts = _decode_pointer(operation.path)
        mapped = list(parts)
        if parts[0] == "widgets":
            if len(parts) == 2 and parts[1] == "-":
                mapped = parts
            elif len(parts) >= 3 and parts[1] == "by-id":
                try:
                    index = _find_id(payload.get("widgets", []), parts[2], "Widget")
                except DashboardPatchError as exc:
                    if operation.op == "add" and len(parts) == 3:
                        raise DashboardPatchError(
                            f"{exc} Create a new widget with add /widgets/- and a "
                            "complete widget object, then reference its id."
                        ) from exc
                    raise
                tail = parts[3:]
                if tail and tail[0] == "parameters":
                    # Older model prompts called widget query parameters simply
                    # ``parameters``.  Schema v1 stores them under
                    # ``query.default_parameters``.  Translate that one legacy
                    # alias here so the model cannot address arbitrary paths.
                    mapped = [
                        "widgets",
                        str(index),
                        "query",
                        "default_parameters",
                        *tail[1:],
                    ]
                else:
                    mapped = ["widgets", str(index), *tail]
            elif len(parts) >= 3 and parts[1].isdigit() and parts[2] == "parameters":
                # Compatibility for proposals produced by the previous prompt.
                # Numeric paths remain forbidden for every other property: only
                # the legacy ``/widgets/{index}/parameters`` alias is accepted.
                index = int(parts[1])
                widgets = payload.get("widgets", [])
                if index >= len(widgets):
                    raise DashboardPatchError(f"Widget index '{index}' does not exist.")
                mapped = [
                    "widgets",
                    str(index),
                    "query",
                    "default_parameters",
                    *parts[3:],
                ]
            else:
                raise DashboardPatchError(
                    "Agent widget paths must use /widgets/by-id/{widget_id}."
                )
        elif parts[0] == "filters":
            if len(parts) == 2 and parts[1] == "-":
                mapped = parts
            elif len(parts) >= 3 and parts[1] == "by-id":
                try:
                    index = _find_id(payload.get("filters", []), parts[2], "Filter")
                except DashboardPatchError as exc:
                    if operation.op == "add" and len(parts) == 3:
                        raise DashboardPatchError(
                            f"{exc} Create a new filter with add /filters/- and a "
                            "complete filter object, then reference its id."
                        ) from exc
                    raise
                mapped = ["filters", str(index), *parts[3:]]
            else:
                raise DashboardPatchError(
                    "Agent filter paths must use /filters/by-id/{filter_id}."
                )
        elif len(parts) >= 5 and parts[:3] == ["layouts", "desktop", "by-widget-id"]:
            index = _find_layout(
                payload.get("layouts", {}).get("desktop", []), parts[3]
            )
            mapped = ["layouts", "desktop", str(index), *parts[4:]]
        path = "/" + "/".join(_encode_pointer(part) for part in mapped)
        translated = DashboardPatchOperation(
            op=operation.op,
            path=path,
            value=operation.value,
        )
        # Use the same bounded patch interpreter as the final application. Do not
        # validate intermediate schemas: related fields can be completed later
        # in this atomic proposal. The caller validates the complete result.
        payload = apply_dashboard_patch(payload, [translated])
        resolved.append(translated)
    return resolved


class DashboardAnnotationService:
    def __init__(
        self,
        dashboard_service: Optional[DashboardService] = None,
        collaboration_service: Optional[DashboardCollaborationService] = None,
    ) -> None:
        self.dashboard_service = dashboard_service or DashboardService()
        self.collaboration_service = (
            collaboration_service
            or DashboardCollaborationService(self.dashboard_service)
        )

    def _to_record(
        self, entity: DashboardAnnotationEntity
    ) -> DashboardAnnotationRecord:
        proposal = (
            model_validate_compat(
                DashboardChangeProposal, json.loads(entity.proposal_json)
            )
            if entity.proposal_json
            else None
        )
        return DashboardAnnotationRecord(
            id=entity.id,
            dashboard_id=entity.dashboard_id,
            actor_id=entity.actor_id,
            conversation_id=entity.conversation_id,
            source_turn_id=entity.source_turn_id,
            base_revision=entity.base_revision,
            target=json.loads(entity.target_json),
            prompt=entity.prompt,
            intent=getattr(entity, "intent", None)
            or DashboardAnnotationIntent.MODIFY.value,
            status=entity.status,
            proposal=proposal,
            created_at=entity.gmt_created,
            updated_at=entity.gmt_modified,
            resolved_at=entity.resolved_at,
        )

    def _get(self, dashboard_id: str, annotation_id: str) -> DashboardAnnotationEntity:
        entity = self.dashboard_service.dao.get_annotation(annotation_id)
        if entity is None or entity.dashboard_id != dashboard_id:
            raise DashboardNotFoundError(annotation_id)
        return entity

    def list_annotations(
        self,
        dashboard_id: str,
        actor_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DashboardAnnotationRecord]:
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.VIEW
        )
        return [
            self._to_record(entity)
            for entity in self.dashboard_service.dao.list_annotations(
                dashboard_id, limit=limit, offset=offset
            )
        ]

    def create_annotation(
        self,
        dashboard_id: str,
        request: DashboardAnnotationCreateRequest,
        actor_id: str,
    ) -> DashboardAnnotationRecord:
        dashboard = self.dashboard_service.get_dashboard(dashboard_id, actor_id)
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        if dashboard.current_revision != request.base_revision:
            raise DashboardConflictError(
                f"Dashboard revision changed from {request.base_revision} "
                f"to {dashboard.current_revision}."
            )
        widget = None
        if request.target.kind == DashboardSelectionKind.DASHBOARD:
            if request.target.widget_id or request.target.filter_id:
                raise DashboardPatchError(
                    "Dashboard selection cannot name a widget or filter."
                )
        elif request.target.kind == DashboardSelectionKind.FILTER:
            if not request.target.filter_id:
                raise DashboardPatchError("Filter selection requires a filter ID.")
            dashboard_filter = next(
                (
                    item
                    for item in dashboard.schema_payload.filters
                    if item.id == request.target.filter_id
                ),
                None,
            )
            if dashboard_filter is None:
                raise DashboardPatchError(
                    f"Filter '{request.target.filter_id}' does not exist."
                )
        else:
            if not request.target.widget_id:
                raise DashboardPatchError("Widget selection requires a widget ID.")
            widget = next(
                (
                    item
                    for item in dashboard.schema_payload.widgets
                    if item.id == request.target.widget_id
                ),
                None,
            )
            if widget is None:
                raise DashboardPatchError(
                    f"Widget '{request.target.widget_id}' does not exist."
                )
        if widget is not None and request.target.kind in {
            DashboardSelectionKind.TABLE_COLUMN,
            DashboardSelectionKind.TABLE_CELL,
        }:
            columns = {item.name for item in widget.query.output_fields}
            if request.target.column not in columns:
                raise DashboardPatchError(
                    f"Column '{request.target.column}' is not declared by the widget."
                )
        target_json = _json_dumps(model_dump_compat(request.target))
        if len(target_json.encode("utf-8")) > MAX_ANNOTATION_TARGET_BYTES:
            raise DashboardPatchError("Annotation selection context is too large.")
        entity = self.dashboard_service.dao.create_annotation(
            DashboardAnnotationEntity(
                id=uuid.uuid4().hex,
                dashboard_id=dashboard_id,
                actor_id=actor_id,
                conversation_id=request.conversation_id or dashboard.conversation_id,
                source_turn_id=request.source_turn_id or dashboard.source_turn_id,
                base_revision=request.base_revision,
                target_json=target_json,
                prompt=request.prompt.strip(),
                intent=request.intent.value,
                status=DashboardAnnotationStatus.PENDING.value,
                gmt_created=datetime.now(),
                gmt_modified=datetime.now(),
            )
        )
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.created",
            target_type="annotation",
            target_id=entity.id,
            details={
                "selection_kind": request.target.kind.value,
                "widget_id": request.target.widget_id,
                "filter_id": request.target.filter_id,
                "base_revision": request.base_revision,
            },
        )
        return self._to_record(entity)

    def propose_change(
        self,
        dashboard_id: str,
        annotation_id: str,
        request: DashboardChangeProposalRequest,
        actor_id: str,
    ) -> DashboardAnnotationRecord:
        entity = self._get(dashboard_id, annotation_id)
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        entity_intent = (
            getattr(entity, "intent", None) or DashboardAnnotationIntent.MODIFY.value
        )
        if entity_intent != DashboardAnnotationIntent.MODIFY.value:
            raise DashboardPatchError(
                "Explanation and anomaly-analysis annotations are read-only and "
                "cannot create dashboard change proposals."
            )
        if entity.status == DashboardAnnotationStatus.APPLIED.value:
            raise DashboardConflictError("The annotation was already applied.")
        dashboard = self.dashboard_service.get_dashboard(dashboard_id, actor_id)
        if dashboard.current_revision != entity.base_revision:
            self.dashboard_service.dao.update_annotation(
                annotation_id,
                status=DashboardAnnotationStatus.INVALIDATED.value,
                resolved_at=datetime.now(),
            )
            raise DashboardConflictError(
                "The dashboard changed after this annotation was created."
            )
        operations = resolve_stable_patch_operations(
            dashboard.schema_payload, request.operations
        )
        try:
            patched = apply_dashboard_patch(
                model_dump_compat(dashboard.schema_payload), operations
            )
            preview_schema = model_validate_compat(DashboardSchemaV1, patched)
        except ValidationError as exc:
            raise DashboardPatchError(f"Proposed schema is invalid: {exc}") from exc
        _validate_requested_filter_binding_change(
            entity.prompt,
            json.loads(entity.target_json),
            dashboard.schema_payload,
            preview_schema,
        )
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.QUERY, preview_schema
        )
        validation = self.dashboard_service.validate_schema(
            preview_schema, execute_queries=True
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)
        proposal = DashboardChangeProposal(
            summary=request.summary,
            operations=operations,
            stable_operations=request.operations,
            before=request.before,
            after=request.after,
            validation=validation,
            preview_schema=preview_schema,
        )
        updated = self.dashboard_service.dao.update_annotation(
            annotation_id,
            status=DashboardAnnotationStatus.PROPOSED.value,
            proposal_json=_json_dumps(model_dump_compat(proposal)),
            resolved_at=None,
        )
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.proposed",
            target_type="annotation",
            target_id=annotation_id,
            details={
                "base_revision": entity.base_revision,
                "operation_count": len(operations),
            },
        )
        return self._to_record(updated)

    def invalidate_pending_proposal(
        self,
        dashboard_id: str,
        annotation_id: str,
        actor_id: str,
        *,
        reason: str,
    ) -> DashboardAnnotationRecord:
        """Stop a failed Agent proposal from remaining pending forever."""

        entity = self._get(dashboard_id, annotation_id)
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        if entity.status != DashboardAnnotationStatus.PENDING.value:
            return self._to_record(entity)
        updated = self.dashboard_service.dao.update_annotation(
            annotation_id,
            status=DashboardAnnotationStatus.INVALIDATED.value,
            resolved_at=datetime.now(),
        )
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.proposal_failed",
            target_type="annotation",
            target_id=annotation_id,
            details={"reason": reason[:500]},
        )
        return self._to_record(updated)

    def apply_annotation(
        self,
        dashboard_id: str,
        annotation_id: str,
        request: DashboardAnnotationApplyRequest,
        actor_id: str,
    ) -> DashboardAnnotationApplyResponse:
        entity = self._get(dashboard_id, annotation_id)
        if entity.status != DashboardAnnotationStatus.PROPOSED.value:
            raise DashboardConflictError("The annotation has no applicable proposal.")
        if entity.proposal_json is None:
            raise DashboardConflictError("The annotation proposal is missing.")
        if request.expected_revision != entity.base_revision:
            raise DashboardConflictError(
                "The proposal must be applied to the revision it was generated from."
            )
        proposal = model_validate_compat(
            DashboardChangeProposal, json.loads(entity.proposal_json)
        )
        validation = self.dashboard_service.validate_schema(
            proposal.preview_schema, execute_queries=True
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)
        operation = self.collaboration_service.apply_operation(
            dashboard_id,
            DashboardOperationRequest(
                operation_id=request.operation_id,
                client_id=request.client_id,
                expected_revision=request.expected_revision,
                promote_to_asset=False,
                operations=proposal.operations,
            ),
            actor_id,
            promote_to_asset=False,
            version_source="ai_annotation",
        )
        updated = self.dashboard_service.dao.update_annotation(
            annotation_id,
            status=DashboardAnnotationStatus.APPLIED.value,
            resolved_at=datetime.now(),
        )
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.applied",
            target_type="annotation",
            target_id=annotation_id,
            details={"applied_revision": operation.dashboard.current_revision},
        )
        return DashboardAnnotationApplyResponse(
            annotation=self._to_record(updated), operation=operation
        )

    def apply_batch(self, dashboard_id, annotation_ids, request, actor_id):
        """Validate all proposals together and save their changes in one revision."""
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        if len(annotation_ids) != len(set(annotation_ids)):
            raise DashboardPatchError("本批次包含重复批注。")
        dashboard = self.dashboard_service.get_dashboard(dashboard_id, actor_id)
        if dashboard.current_revision != request.expected_revision:
            raise DashboardConflictError("看板已发生变化，请重新生成本批修改。")
        payload = model_dump_compat(dashboard.schema_payload)
        operations, seen = [], {}
        for annotation_id in annotation_ids:
            entity = self._get(dashboard_id, annotation_id)
            if (
                entity.status != DashboardAnnotationStatus.PROPOSED.value
                or not entity.proposal_json
            ):
                raise DashboardConflictError("本批次仍有批注没有可应用的方案。")
            if entity.base_revision != request.expected_revision:
                raise DashboardConflictError("本批方案来自不同修订，请重新生成。")
            proposal = model_validate_compat(
                DashboardChangeProposal, json.loads(entity.proposal_json)
            )
            if not proposal.stable_operations:
                raise DashboardPatchError("此历史方案不支持批量应用，请重新生成。")
            proposal_paths, stable_operations = {}, []
            for stable in proposal.stable_operations:
                signature = (stable.op, _json_dumps(stable.value))
                if stable.path in seen and seen[stable.path] == signature:
                    continue
                if any(
                    stable.path == path
                    or stable.path.startswith(path + "/")
                    or path.startswith(stable.path + "/")
                    for path in seen
                ):
                    raise DashboardPatchError(
                        "多条批注对同一设置提出了不同修改，请在对话中统一要求。"
                    )
                proposal_paths[stable.path] = signature
                stable_operations.append(stable)
            # Ordered edits within one validated proposal may depend on each
            # other. Conflict checks apply between separate annotations only.
            resolved = resolve_stable_patch_operations(
                model_validate_compat(DashboardSchemaV1, payload), stable_operations
            )
            payload = apply_dashboard_patch(payload, resolved)
            operations.extend(resolved)
            seen.update(proposal_paths)
        schema = model_validate_compat(DashboardSchemaV1, payload)
        self.dashboard_service.authorize_schema_sources(actor_id, schema)
        validation = self.dashboard_service.validate_schema(
            schema, execute_queries=True
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)
        operation = self.collaboration_service.apply_operation(
            dashboard_id,
            DashboardOperationRequest(
                operation_id=request.operation_id,
                client_id=request.client_id,
                expected_revision=request.expected_revision,
                promote_to_asset=False,
                operations=operations,
            ),
            actor_id,
            promote_to_asset=False,
            version_source="ai_annotation",
        )
        updated = [
            self._to_record(
                self.dashboard_service.dao.update_annotation(
                    annotation_id,
                    status=DashboardAnnotationStatus.APPLIED.value,
                    resolved_at=datetime.now(),
                )
            )
            for annotation_id in annotation_ids
        ]
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.batch_applied",
            details={
                "annotation_ids": annotation_ids,
                "applied_revision": operation.dashboard.current_revision,
            },
        )
        return {"annotations": updated, "operation": operation}

    def reject_annotation(
        self, dashboard_id: str, annotation_id: str, actor_id: str
    ) -> DashboardAnnotationRecord:
        entity = self._get(dashboard_id, annotation_id)
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        if entity.status == DashboardAnnotationStatus.APPLIED.value:
            raise DashboardConflictError("An applied annotation cannot be rejected.")
        updated = self.dashboard_service.dao.update_annotation(
            annotation_id,
            status=DashboardAnnotationStatus.REJECTED.value,
            resolved_at=datetime.now(),
        )
        self.dashboard_service.record_audit(
            dashboard_id,
            actor_id,
            "annotation.rejected",
            target_type="annotation",
            target_id=annotation_id,
            details={"base_revision": entity.base_revision},
        )
        return self._to_record(updated)
