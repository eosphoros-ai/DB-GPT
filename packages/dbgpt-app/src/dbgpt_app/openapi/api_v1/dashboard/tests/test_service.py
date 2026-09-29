import asyncio
import hashlib
import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

import dbgpt_app.openapi.api_v1.dashboard.service as dashboard_service_module
from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.demo_contracts import (
    normalize_verified_olist_plan,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardConflictError,
    DashboardDao,
    DashboardEntity,
    DashboardRevisionEntity,
    DashboardShareEntity,
)
from dbgpt_app.openapi.api_v1.dashboard.planner import DashboardPlannerService
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardAssetState,
    DashboardCreateRequest,
    DashboardOrigin,
    DashboardPlan,
    DashboardQueryDraftRequest,
    DashboardSchemaV1,
    DashboardVisualTheme,
)
from dbgpt_app.openapi.api_v1.dashboard.service import (
    DashboardPublishValidationError,
    DashboardSchemaValidationError,
    DashboardService,
)
from dbgpt_app.openapi.api_v1.tools.dashboard import (
    _draft_validation_message,
    _normalize_model_query_payload,
    _validate_generated_filter_contract,
    make_dashboard_planner_tools,
)

_MONTHLY_SALES_SQL = "SELECT month, SUM(sales) AS sales FROM sales GROUP BY month"


def schema_payload():
    return {
        "schema_version": "1.3",
        "dashboard": {
            "title": "Retail sales",
            "description": "A deterministic fixture",
            "data_source_id": "walmart",
        },
        "metric_context": {
            "grain": "store-week",
            "data_freshness": "fixture",
            "source_notes": ["test fixture"],
        },
        "filters": [
            {
                "id": "date",
                "type": "date_range",
                "label": "Date",
                "field": "date",
                "default": ["2010-01-01", "2012-12-31"],
            }
        ],
        "widgets": [
            {
                "id": "total-sales",
                "type": "kpi",
                "title": "Total sales",
                "query": {
                    "data_source_id": "walmart",
                    "sql": (
                        "SELECT SUM(sales) AS total_sales FROM sales "
                        "WHERE date BETWEEN :start_date AND :end_date"
                    ),
                    "filter_parameters": {
                        "date": {
                            "start_parameter": "start_date",
                            "end_parameter": "end_date",
                        }
                    },
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "max_rows": 10,
                },
                "publication": {
                    "query": {
                        "data_source_id": "walmart",
                        "sql": (
                            "SELECT date, sales FROM sales "
                            "WHERE 1 = 1 /* publication_sales */ ORDER BY date"
                        ),
                        "output_fields": [
                            {"name": "date", "type": "date"},
                            {"name": "sales", "type": "number"},
                        ],
                        "max_rows": 100,
                    },
                    "filter_fields": {"date": "date"},
                    "measures": [
                        {
                            "source_field": "sales",
                            "output_field": "total_sales",
                            "aggregation": "sum",
                        }
                    ],
                    "output_columns": ["total_sales"],
                    "max_output_rows": 1,
                },
                "encoding": {"value": "total_sales"},
            },
            {
                "id": "sales-trend",
                "type": "line",
                "title": "Sales trend",
                "query": {
                    "data_source_id": "walmart",
                    "sql": _MONTHLY_SALES_SQL,
                    "output_fields": [
                        {"name": "month", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "max_rows": 10,
                },
                "publication": {
                    "query": {
                        "data_source_id": "walmart",
                        "sql": (
                            "SELECT date AS month, sales FROM sales "
                            "WHERE 1 = 1 /* publication_trend */ ORDER BY date"
                        ),
                        "output_fields": [
                            {"name": "month", "type": "date"},
                            {"name": "sales", "type": "number"},
                        ],
                        "max_rows": 100,
                    },
                    "filter_fields": {"date": "month"},
                    "group_by": ["month"],
                    "measures": [
                        {
                            "source_field": "sales",
                            "output_field": "sales",
                            "aggregation": "sum",
                        }
                    ],
                    "output_columns": ["month", "sales"],
                    "max_output_rows": 100,
                },
                "encoding": {"x": "month", "y": "sales"},
            },
        ],
        "layouts": {
            "desktop": [
                {"widget_id": "total-sales", "x": 0, "y": 0, "w": 4, "h": 3},
                {"widget_id": "sales-trend", "x": 4, "y": 0, "w": 8, "h": 5},
            ]
        },
    }


class FakeConnector:
    db_type = "sqlite"

    def __init__(self):
        self.calls = []

    def get_table_names(self):
        return ["sales"]

    def get_fields(self, table, database=None):
        return [
            ("date", "date"),
            ("month", "text"),
            ("store", "integer"),
            ("holiday", "text"),
            ("holiday_flag", "text"),
            ("sales", "real"),
        ]

    def query_ex(self, sql, params=None, timeout=None):
        self.calls.append({"sql": sql, "params": params, "timeout": timeout})
        if "runtime_fail" in sql:
            raise RuntimeError("simulated database timeout")
        if "empty_result" in sql:
            return ["month", "sales"], []
        if "publication_sales" in sql:
            return ["date", "sales"], [
                ("2010-01-15", 10.0),
                ("2011-01-15", 20.0),
            ]
        if "publication_trend" in sql:
            return ["month", "sales"], [
                ("2010-01-15", 10.0),
                ("2011-01-15", 20.0),
            ]
        if "date, store, holiday AS holiday_flag, sales" in sql:
            return ["date", "store", "holiday_flag", "sales"], [
                ("2024-01-01", 1, "0", 100.0),
                ("2024-01-02", 2, "1", 120.0),
            ]
        if "SELECT store, sales FROM sales" in sql:
            return ["store", "sales"], [(1, 100.0), (2, 120.0)]
        if "total_sales" in sql:
            return ["total_sales"], [(1234.5,)]
        return ["month", "sales"], [("01", 100.0), ("02", 120.0)]


class FakeDao:
    def remember_share_token(self, token):
        import hashlib

        self.remembered_token_hash = hashlib.sha256(token.encode()).hexdigest()

    def __init__(self):
        self.rows = {}
        self.revisions = []
        self.shares = []

    @staticmethod
    def _copy(row):
        return DashboardEntity(
            id=row.id,
            owner_id=row.owner_id,
            conversation_id=row.conversation_id,
            source_turn_id=row.source_turn_id,
            origin=row.origin,
            asset_state=row.asset_state,
            saved_at=row.saved_at,
            title=row.title,
            description=row.description,
            data_source_id=row.data_source_id,
            schema_json=row.schema_json,
            current_revision=row.current_revision,
            status=row.status,
            public_slug=row.public_slug,
            gmt_created=row.gmt_created,
            gmt_modified=row.gmt_modified,
        )

    def create_dashboard(self, entity):
        self.rows[entity.id] = self._copy(entity)
        return self._copy(entity)

    def get_dashboard(self, dashboard_id, owner_id=None):
        row = self.rows.get(dashboard_id)
        if not row or (owner_id is not None and owner_id != row.owner_id):
            return None
        return self._copy(row)

    def get_dashboard_by_id(self, dashboard_id):
        return self.get_dashboard(dashboard_id)

    def get_dashboard_by_public_slug(self, public_slug):
        row = next(
            (item for item in self.rows.values() if item.public_slug == public_slug),
            None,
        )
        return self._copy(row) if row is not None else None

    def list_dashboards(self, owner_id, **filters):
        rows = [row for row in self.rows.values() if row.owner_id == owner_id]
        for name in ("conversation_id", "origin", "asset_state", "status"):
            value = filters.get(name)
            if value is not None:
                rows = [row for row in rows if getattr(row, name) == value]
        excluded_origin = filters.get("exclude_origin")
        if excluded_origin is not None:
            rows = [row for row in rows if row.origin != excluded_origin]
        return [self._copy(row) for row in rows]

    def update_dashboard(self, dashboard_id, owner_id, expected_revision, **values):
        row = self.rows[dashboard_id]
        if row.owner_id != owner_id:
            raise LookupError(dashboard_id)
        if row.current_revision != expected_revision:
            raise DashboardConflictError("revision conflict")
        row.title = values["title"]
        row.description = values["description"]
        row.data_source_id = values["data_source_id"]
        row.schema_json = values["schema_json"]
        row.current_revision += 1
        row.status = "draft"
        if values.get("promote_to_asset", True):
            row.asset_state = "saved"
            row.saved_at = row.saved_at or datetime.now()
        row.gmt_modified = datetime.now()
        return self._copy(row)

    def publish_dashboard(
        self,
        dashboard_id,
        owner_id,
        expected_revision,
        *,
        schema_json,
        snapshot_json,
        validation_json,
        share_token_hash,
        public_slug=None,
        share_created_by=None,
        share_expires_at=None,
    ):
        row = self.rows[dashboard_id]
        if row.owner_id != owner_id or row.current_revision != expected_revision:
            raise DashboardConflictError("revision conflict")
        revision = DashboardRevisionEntity(
            id=len(self.revisions) + 1,
            dashboard_id=dashboard_id,
            revision=len(self.revisions) + 1,
            schema_json=schema_json,
            snapshot_json=snapshot_json,
            validation_json=validation_json,
            share_token_hash=share_token_hash,
            gmt_published=datetime.now(),
        )
        self.revisions.append(revision)
        self.shares.append(
            DashboardShareEntity(
                id=len(self.shares) + 1,
                dashboard_id=dashboard_id,
                revision=revision.revision,
                token_hash=share_token_hash,
                created_by=share_created_by or row.owner_id,
                expires_at=share_expires_at,
                revoked_at=None,
                gmt_created=datetime.now(),
            )
        )
        row.status = "published"
        row.public_slug = row.public_slug or public_slug
        row.asset_state = "saved"
        row.saved_at = row.saved_at or datetime.now()
        return revision, self._copy(row)

    def get_published_by_token_hash(self, token_hash):
        return next(
            (item for item in self.revisions if item.share_token_hash == token_hash),
            None,
        )

    def list_published_revisions(self, dashboard_id):
        return sorted(
            (item for item in self.revisions if item.dashboard_id == dashboard_id),
            key=lambda item: item.revision,
            reverse=True,
        )

    def get_latest_published_revision(self, dashboard_id):
        revisions = self.list_published_revisions(dashboard_id)
        return revisions[0] if revisions else None

    def get_active_published_by_token_hash(self, token_hash, now=None):
        now = now or datetime.now()
        share = next(
            (
                item
                for item in self.shares
                if item.token_hash == token_hash
                and item.revoked_at is None
                and (item.expires_at is None or item.expires_at > now)
            ),
            None,
        )
        if share is None:
            return None
        return next(
            item
            for item in self.revisions
            if item.dashboard_id == share.dashboard_id
            and item.revision == share.revision
        )

    def list_shares(self, dashboard_id):
        return [item for item in self.shares if item.dashboard_id == dashboard_id]

    def rotate_share(
        self,
        dashboard_id,
        revision,
        token_hash,
        *,
        created_by,
        expires_at=None,
    ):
        now = datetime.now()
        for item in self.shares:
            if (
                item.dashboard_id == dashboard_id
                and item.revision == revision
                and item.revoked_at is None
            ):
                item.revoked_at = now
        share = DashboardShareEntity(
            id=len(self.shares) + 1,
            dashboard_id=dashboard_id,
            revision=revision,
            token_hash=token_hash,
            created_by=created_by,
            expires_at=expires_at,
            revoked_at=None,
            gmt_created=now,
        )
        self.shares.append(share)
        return share

    def revoke_shares(self, dashboard_id, revision):
        now = datetime.now()
        count = 0
        for item in self.shares:
            if (
                item.dashboard_id == dashboard_id
                and item.revision == revision
                and item.revoked_at is None
            ):
                item.revoked_at = now
                count += 1
        return count


@pytest.fixture
def service_fixture():
    connector = FakeConnector()
    dao = FakeDao()
    return (
        DashboardService(dao=dao, connector_resolver=lambda _: connector),
        dao,
        connector,
    )


def create_record(service):
    request = DashboardCreateRequest(
        schema=DashboardSchemaV1.model_validate(schema_payload())
    )
    return service.create_dashboard(request, "alice")


def test_create_save_and_optimistic_conflict(service_fixture):
    service, _, _ = service_fixture
    created = create_record(service)
    assert created.current_revision == 1
    assert created.schema_payload.dashboard.id == created.id

    changed = created.schema_payload.model_copy(deep=True)
    changed.dashboard.title = "Updated title"
    saved = service.update_dashboard(created.id, changed, 1, "alice")
    assert saved.current_revision == 2
    assert saved.schema_payload.dashboard.title == "Updated title"
    with pytest.raises(DashboardConflictError):
        service.update_dashboard(created.id, changed, 1, "alice")


def test_edit_version_history_is_immutable_and_restore_appends_new_revision():
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    service = DashboardService(
        dao=DashboardDao(manager), connector_resolver=lambda _: FakeConnector()
    )
    created = create_record(service)
    changed = created.schema_payload.model_copy(deep=True)
    changed.dashboard.title = "Updated title"
    saved = service.update_dashboard(created.id, changed, 1, "alice")

    versions = service.list_edit_versions(created.id, "alice")
    assert [item.revision for item in versions] == [2, 1]
    assert versions[0].source == "manual_save"
    original = service.get_edit_version(created.id, 1, "alice")
    assert original.schema_payload.dashboard.title == "Retail sales"

    restored = service.restore_edit_version(
        created.id, 1, saved.current_revision, "alice"
    )

    assert restored.current_revision == 3
    assert restored.schema_payload.dashboard.title == "Retail sales"
    after = service.list_edit_versions(created.id, "alice")
    assert [item.revision for item in after] == [3, 2, 1]
    assert after[0].source == "edit_version_restore"
    changed_version = service.get_edit_version(created.id, 2, "alice")
    assert changed_version.schema_payload.dashboard.title == "Updated title"


def test_artifact_bundle_contains_schema_plan_queries_readme_and_manifest(
    service_fixture,
):
    service, _, _ = service_fixture
    payload = schema_payload()
    payload["metadata"] = {
        "compatibility": {
            "dashboard_plan": {
                "title": "Retail plan",
                "decision_goal": "Choose an intervention",
            }
        }
    }
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    bundle = service.build_artifact_bundle(record.id, "alice")
    files = {item.path: item.content for item in bundle.files}

    assert {
        "dashboard.schema.json",
        "dashboard.plan.json",
        "queries/total-sales.sql",
        "queries/sales-trend.sql",
        "README.md",
        "manifest.json",
    } <= set(files)
    assert "SELECT SUM(sales)" in files["queries/total-sales.sql"]
    manifest = json.loads(files["manifest.json"])
    assert manifest["files"][-1] == "manifest.json"
    assert set(manifest["files"]) == set(files)
    assert manifest["theme"] == {
        "preset": "clarity",
        "mode": "light",
        "overrides": {},
    }
    assert "Visual theme: `clarity` / `light`" in files["README.md"]
    exported_schema = json.loads(files["dashboard.schema.json"])
    assert "theme" in exported_schema["dashboard"]


def test_agent_generated_draft_stays_out_of_asset_library_until_first_save(
    service_fixture,
):
    service, _, _ = service_fixture
    request = DashboardCreateRequest(
        schema=DashboardSchemaV1.model_validate(schema_payload()),
        conversation_id="conversation-one",
        source_turn_id="turn-one",
    )

    generated = service.create_agent_dashboard(request, "alice")

    assert generated.origin == DashboardOrigin.TASK
    assert generated.asset_state == DashboardAssetState.GENERATED
    assert generated.saved_at is None
    assert generated.conversation_id == "conversation-one"
    assert generated.source_turn_id == "turn-one"
    assert service.list_dashboards("alice") == []
    assert [
        item.id
        for item in service.list_dashboards(
            "alice", conversation_id="conversation-one", include_generated=True
        )
    ] == [generated.id]

    saved = service.update_dashboard(
        generated.id, generated.schema_payload, generated.current_revision, "alice"
    )

    assert saved.asset_state == DashboardAssetState.SAVED
    assert saved.saved_at is not None
    assert [item.id for item in service.list_dashboards("alice")] == [generated.id]


def test_same_conversation_keeps_distinct_dashboard_turn_references(service_fixture):
    service, _, _ = service_fixture
    first = service.create_agent_dashboard(
        DashboardCreateRequest(
            schema=DashboardSchemaV1.model_validate(schema_payload()),
            conversation_id="conversation-many",
            source_turn_id="turn-a",
        ),
        "alice",
    )
    second_schema = DashboardSchemaV1.model_validate(schema_payload())
    second_schema.dashboard.title = "Second board"
    second = service.create_agent_dashboard(
        DashboardCreateRequest(
            schema=second_schema,
            conversation_id="conversation-many",
            source_turn_id="turn-b",
        ),
        "alice",
    )

    restored = service.list_dashboards(
        "alice", conversation_id="conversation-many", include_generated=True
    )
    assert {item.id for item in restored} == {first.id, second.id}
    assert {item.source_turn_id for item in restored} == {"turn-a", "turn-b"}


def test_asset_library_can_exclude_templates(service_fixture):
    service, _, _ = service_fixture
    mine = create_record(service)
    template = service.create_dashboard(
        DashboardCreateRequest(
            schema=DashboardSchemaV1.model_validate(schema_payload()),
            origin=DashboardOrigin.TEMPLATE,
        ),
        "alice",
    )

    items = service.list_dashboards("alice", exclude_origin=DashboardOrigin.TEMPLATE)

    assert [item.id for item in items] == [mine.id]
    assert template.id not in {item.id for item in items}


def test_refresh_binds_date_values_and_keeps_widgets_independent(service_fixture):
    service, _, connector = service_fixture
    record = create_record(service)
    snapshot = service.refresh_dashboard(
        record.id, {"date": ["2011-01-01", "2011-12-31"]}, "alice"
    )
    assert snapshot.widgets["total-sales"].rows == [[1234.5]]
    assert snapshot.widgets["sales-trend"].row_count == 2
    first_call = connector.calls[0]
    assert first_call["params"] == {
        "start_date": "2011-01-01",
        "end_date": "2011-12-31",
    }
    assert first_call["sql"].endswith("LIMIT 11")


def test_parameter_resolution_uses_user_filter_component_and_all_priority(
    service_fixture,
):
    service, _, connector = service_fixture
    payload = schema_payload()
    payload["filters"].append(
        {
            "id": "fiscal_year",
            "type": "select",
            "label": "Fiscal year",
            "field": "fiscal_year",
            "default": "2024",
            "options": [
                {"label": "2024", "value": "2024"},
                {"label": "2025", "value": "2025"},
            ],
        }
    )
    query = payload["widgets"][0]["query"]
    query["sql"] += " AND (:fiscal_year IS NULL OR :fiscal_year = :fiscal_year)"
    # Reproduce the legacy planner mismatch that caused the Apple dashboard to
    # map one name while emitting a different SQL placeholder.
    query["filter_parameters"]["fiscal_year"] = "fiscal_year_filter"
    query["default_parameters"] = {"fiscal_year": "2023"}
    schema = DashboardSchemaV1.model_validate(payload)

    service.validate_widget_query(schema, "total-sales", {"fiscal_year": "2025"})
    assert connector.calls[-1]["params"]["fiscal_year"] == "2025"

    service.validate_widget_query(schema, "total-sales", {})
    assert connector.calls[-1]["params"]["fiscal_year"] == "2024"

    schema.filters[-1].default = None
    service.validate_widget_query(schema, "total-sales", {})
    assert connector.calls[-1]["params"]["fiscal_year"] == "2023"

    schema.widgets[0].query.default_parameters = {}
    service.validate_widget_query(schema, "total-sales", {})
    assert connector.calls[-1]["params"]["fiscal_year"] is None

    schema.widgets[0].query.default_parameters = {"fiscal_year": "2023"}
    service.validate_widget_query(schema, "total-sales", {"fiscal_year": None})
    assert connector.calls[-1]["params"]["fiscal_year"] is None


@pytest.mark.parametrize(
    ("selected_stores", "expected_bound_values"),
    [
        ([], []),
        ([1], [1]),
        ([1, 2], [1, 2]),
        ([1, 2, 3], [1, 2, 3]),
    ],
)
def test_refresh_handles_legacy_optional_multi_select_filter(
    service_fixture, selected_stores, expected_bound_values
):
    service, _, connector = service_fixture
    payload = schema_payload()
    payload["filters"].append(
        {
            "id": "stores",
            "type": "multi_select",
            "label": "Stores",
            "field": "store",
            "default": [],
            "options": [
                {"label": "Store 1", "value": 1},
                {"label": "Store 2", "value": 2},
                {"label": "Store 3", "value": 3},
            ],
        }
    )
    payload["widgets"][0]["query"]["sql"] = (
        "SELECT SUM(sales) AS total_sales FROM sales "
        "WHERE date BETWEEN :start_date AND :end_date "
        "AND (:store_ids IS NULL OR store IN (:store_ids))"
    )
    payload["widgets"][0]["query"]["filter_parameters"]["stores"] = "store_ids"
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    snapshot = service.refresh_dashboard(
        record.id,
        {
            "date": ["2011-01-01", "2011-12-31"],
            "stores": selected_stores,
        },
        "alice",
    )

    assert snapshot.widgets["total-sales"].error is None
    call = next(item for item in connector.calls if "total_sales" in item["sql"])
    bound_values = [
        value
        for name, value in call["params"].items()
        if name.startswith("__dbgpt_store_ids_")
    ]
    assert bound_values == expected_bound_values
    if selected_stores:
        assert "IS NULL" not in call["sql"].upper()
        assert " IN (" in call["sql"].upper()
    else:
        assert "TRUE" in call["sql"].upper()


def test_result_field_validation_is_case_insensitive():
    class UppercaseConnector(FakeConnector):
        def query_ex(self, sql, params=None, timeout=None):
            self.calls.append({"sql": sql, "params": params, "timeout": timeout})
            if "total_sales" in sql:
                return ["TOTAL_SALES"], [(1234.5,)]
            return ["MONTH", "SALES"], [("01", 100.0)]

    connector = UppercaseConnector()
    service = DashboardService(dao=FakeDao(), connector_resolver=lambda _: connector)
    record = create_record(service)

    snapshot = service.refresh_dashboard(record.id, {}, "alice")

    assert snapshot.widgets["total-sales"].error is None
    assert snapshot.widgets["sales-trend"].error is None


def test_case_only_duplicate_result_fields_fail_as_ambiguous():
    class AmbiguousConnector(FakeConnector):
        def query_ex(self, sql, params=None, timeout=None):
            return ["sales", "SALES"], [(1, 2)]

    connector = AmbiguousConnector()
    service = DashboardService(dao=FakeDao(), connector_resolver=lambda _: connector)
    payload = schema_payload()
    payload["widgets"] = [payload["widgets"][0]]
    payload["layouts"]["desktop"] = [payload["layouts"]["desktop"][0]]
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    snapshot = service.refresh_dashboard(record.id, {}, "alice")

    assert "ambiguous columns" in snapshot.widgets["total-sales"].error.message


def test_one_widget_failure_does_not_discard_successful_widgets(service_fixture):
    service, _, _ = service_fixture
    payload = schema_payload()
    payload["widgets"][1]["query"]["sql"] = (
        "SELECT SUM(sales) AS runtime_fail FROM sales"
    )
    payload["widgets"][1]["query"]["output_fields"] = [
        {"name": "runtime_fail", "type": "number"}
    ]
    payload["widgets"][1]["encoding"] = {"x": "runtime_fail", "y": "runtime_fail"}
    # This test isolates live refresh degradation, not publication datasets.
    payload["widgets"][1].pop("publication", None)
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )
    snapshot = service.refresh_dashboard(record.id, {}, "alice")
    assert snapshot.widgets["total-sales"].error is None
    assert snapshot.widgets["sales-trend"].error is not None
    assert "simulated database timeout" in snapshot.widgets["sales-trend"].error.message


def test_publish_stores_only_token_hash_and_public_read_never_queries_database(
    service_fixture,
):
    service, dao, connector = service_fixture
    record = create_record(service)
    published = service.publish_dashboard(record.id, 1, {}, "alice")
    assert published.share_token
    assert (
        dao.revisions[0].share_token_hash
        == hashlib.sha256(published.share_token.encode("utf-8")).hexdigest()
    )
    assert published.share_token not in dao.revisions[0].share_token_hash

    query_count = len(connector.calls)
    public = service.get_public_snapshot(published.share_token)
    assert public.dashboard_id == record.id
    assert public.snapshot.widgets["total-sales"].rows == [[1234.5]]
    assert len(connector.calls) == query_count


def test_publish_persists_deterministic_anomaly_evidence_in_immutable_snapshot(
    service_fixture,
):
    service, dao, connector = service_fixture
    payload = schema_payload()
    payload["widgets"][1]["anomaly_rules"] = [
        {
            "id": "sales-change",
            "label": "Sales period change",
            "baseline": "previous_period",
            "value_field": "sales",
            "time_field": "month",
            "direction": "two_sided",
            "threshold": {"mode": "relative_change", "value": 0.1},
        }
    ]
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    published = service.publish_dashboard(record.id, 1, {}, "alice")
    stored = json.loads(dao.revisions[0].snapshot_json)
    stored_evidence = stored["widgets"]["sales-trend"]["anomalies"][0]

    assert stored_evidence["status"] == "anomaly"
    assert stored_evidence["current_value"] == 120.0
    assert stored_evidence["baseline_value"] == 100.0
    assert stored_evidence["change_ratio"] == 0.2
    assert stored_evidence["sample_size"] == 2
    query_count = len(connector.calls)
    public = service.get_public_snapshot(published.share_token)
    assert public.snapshot.widgets["sales-trend"].anomalies[0].matched_rule == (
        "abs(change_ratio) >= 0.1"
    )
    assert len(connector.calls) == query_count


def test_public_filter_recomputes_from_frozen_revision_without_database(
    service_fixture,
):
    service, dao, connector = service_fixture
    payload = schema_payload()
    payload["schema_version"] = "1.3"
    payload["widgets"][0]["publication"] = {
        "query": {
            "data_source_id": "walmart",
            "sql": (
                "SELECT date, sales FROM sales "
                "WHERE 1 = 1 /* publication_sales */ ORDER BY date"
            ),
            "output_fields": [
                {"name": "date", "type": "date"},
                {"name": "sales", "type": "number"},
            ],
            "max_rows": 100,
        },
        "filter_fields": {"date": "date"},
        "measures": [
            {
                "source_field": "sales",
                "output_field": "total_sales",
                "aggregation": "sum",
            }
        ],
        "output_columns": ["total_sales"],
        "max_output_rows": 1,
    }
    payload["widgets"][1]["publication"] = {
        "query": {
            "data_source_id": "walmart",
            "sql": (
                "SELECT date AS month, sales FROM sales "
                "WHERE 1 = 1 /* publication_trend */ ORDER BY date"
            ),
            "output_fields": [
                {"name": "month", "type": "date"},
                {"name": "sales", "type": "number"},
            ],
            "max_rows": 100,
        },
        "filter_fields": {"date": "month"},
        "group_by": ["month"],
        "measures": [
            {
                "source_field": "sales",
                "output_field": "sales",
                "aggregation": "sum",
            }
        ],
        "output_columns": ["month", "sales"],
        "max_output_rows": 100,
    }
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )
    published = service.publish_dashboard(record.id, 1, {}, "alice")

    stored_snapshot = json.loads(dao.revisions[0].snapshot_json)
    assert stored_snapshot["publication_datasets"]["total-sales"]["row_count"] == 2
    public = service.get_public_snapshot(published.share_token)
    assert public.snapshot.publication_datasets == {}

    query_count = len(connector.calls)
    filtered = service.filter_public_snapshot(
        published.share_token,
        {"date": ["2010-01-01", "2010-12-31"]},
    )

    assert filtered.snapshot.widgets["total-sales"].rows == [[10]]
    assert filtered.snapshot.widgets["sales-trend"].rows == [["2010-01-15", 10]]
    assert filtered.unsupported_widget_ids == []
    assert filtered.snapshot.publication_datasets == {}
    assert len(connector.calls) == query_count


def test_filtered_schema_publish_requires_every_widget_binding(service_fixture):
    service, _, connector = service_fixture
    payload = schema_payload()
    payload["schema_version"] = "1.3"
    for widget in payload["widgets"]:
        widget.pop("publication", None)
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    query_count = len(connector.calls)
    with pytest.raises(DashboardPublishValidationError) as exc_info:
        service.publish_dashboard(record.id, 1, {}, "alice")

    assert {issue.code for issue in exc_info.value.result.issues} == {
        "publication_binding_required"
    }
    assert {issue.path for issue in exc_info.value.result.issues} == {
        "widgets.total-sales.publication",
        "widgets.sales-trend.publication",
    }
    assert len(connector.calls) == query_count


def test_publish_button_validation_reports_every_broken_publication_dataset(
    service_fixture,
):
    service, _, _ = service_fixture
    payload = schema_payload()
    for widget in payload["widgets"]:
        widget["publication"]["query"]["sql"] += " /* runtime_fail */"
    schema = DashboardSchemaV1.model_validate(payload)

    validation = service.validate_schema(
        schema,
        execute_queries=True,
        require_publication_bindings=True,
    )

    failures = [
        issue
        for issue in validation.issues
        if issue.code == "publication_materialization_failed"
    ]
    assert validation.valid is False
    assert {issue.path for issue in failures} == {
        "widgets.total-sales.publication",
        "widgets.sales-trend.publication",
    }


def test_owner_can_explicitly_publish_a_safe_static_snapshot(service_fixture):
    service, _, connector = service_fixture
    payload = schema_payload()
    payload["schema_version"] = "1.3"
    for widget in payload["widgets"]:
        widget.pop("publication", None)
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )

    published = service.publish_dashboard(
        record.id,
        1,
        {},
        "alice",
        allow_static_widgets=True,
    )
    public = service.get_public_snapshot(published.share_token)
    query_count = len(connector.calls)
    filtered = service.filter_public_snapshot(
        published.share_token,
        {"date": ["2010-01-01", "2010-12-31"]},
    )

    assert filtered.unsupported_widget_ids == ["total-sales", "sales-trend"]
    assert filtered.snapshot.widgets == public.snapshot.widgets
    assert len(connector.calls) == query_count


def test_publish_promotes_generated_draft_to_saved_asset(service_fixture):
    service, _, _ = service_fixture
    generated = service.create_agent_dashboard(
        DashboardCreateRequest(
            schema=DashboardSchemaV1.model_validate(schema_payload()),
            conversation_id="conversation-publish",
            source_turn_id="turn-publish",
        ),
        "alice",
    )

    service.publish_dashboard(generated.id, generated.current_revision, {}, "alice")
    published = service.get_dashboard(generated.id, "alice")

    assert published.status.value == "published"
    assert published.asset_state == DashboardAssetState.SAVED
    assert published.saved_at is not None


def test_authenticated_editor_restores_latest_published_snapshot_without_querying(
    service_fixture,
):
    service, _, connector = service_fixture
    record = create_record(service)
    service.publish_dashboard(record.id, 1, {}, "alice")

    query_count = len(connector.calls)
    snapshot = service.get_latest_published_snapshot(record.id, "alice")

    assert snapshot.widgets["total-sales"].rows == [[1234.5]]
    assert len(connector.calls) == query_count


def test_republish_keeps_the_first_public_snapshot_immutable(service_fixture):
    service, dao, _ = service_fixture
    record = create_record(service)
    first = service.publish_dashboard(record.id, 1, {}, "alice")

    changed = record.schema_payload.model_copy(deep=True)
    changed.dashboard.title = "Updated private draft"
    saved = service.update_dashboard(record.id, changed, 1, "alice")
    second = service.publish_dashboard(record.id, saved.current_revision, {}, "alice")

    first_public = service.get_public_snapshot(first.share_token)
    second_public = service.get_public_snapshot(second.share_token)
    latest_token = second.latest_share_path.rsplit("/", 1)[-1]
    latest_public = service.get_public_snapshot(latest_token)

    assert first_public.published_revision == 1
    assert first_public.is_latest_link is False
    assert first_public.schema_payload.dashboard.title == "Retail sales"
    assert second_public.published_revision == 2
    assert second_public.schema_payload.dashboard.title == "Updated private draft"
    assert first.latest_share_path == second.latest_share_path
    assert latest_public.published_revision == 2
    assert latest_public.is_latest_link is True
    assert latest_public.schema_payload.dashboard.title == "Updated private draft"
    assert len(dao.revisions) == 2


def test_republish_freezes_each_visual_theme_and_moves_only_the_latest_link(
    service_fixture,
):
    service, dao, _ = service_fixture
    payload = schema_payload()
    payload["schema_version"] = "1.4"
    payload["dashboard"]["theme"] = {
        "preset": "clarity",
        "mode": "light",
        "overrides": {},
    }
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )
    first = service.publish_dashboard(record.id, 1, {}, "alice")

    changed = record.schema_payload.model_copy(deep=True)
    changed.dashboard.theme = DashboardVisualTheme(
        preset="graphite", mode="dark", overrides={}
    )
    saved = service.update_dashboard(record.id, changed, 1, "alice")
    second = service.publish_dashboard(record.id, saved.current_revision, {}, "alice")

    first_public = service.get_public_snapshot(first.share_token)
    second_public = service.get_public_snapshot(second.share_token)
    latest_public = service.get_public_snapshot(
        second.latest_share_path.rsplit("/", 1)[-1]
    )

    assert first_public.schema_payload.dashboard.theme.preset.value == "clarity"
    assert first_public.schema_payload.dashboard.theme.mode.value == "light"
    assert second_public.schema_payload.dashboard.theme.preset.value == "graphite"
    assert second_public.schema_payload.dashboard.theme.mode.value == "dark"
    assert latest_public.schema_payload.dashboard.theme.preset.value == "graphite"
    assert len(dao.revisions) == 2


def test_publication_can_expire_rotate_and_revoke_without_mutating_snapshot(
    service_fixture, monkeypatch
):
    service, dao, connector = service_fixture
    record = create_record(service)
    published = service.publish_dashboard(
        record.id,
        1,
        {},
        "alice",
        share_expires_in_seconds=60,
    )
    assert published.expires_at is not None
    assert service.get_public_snapshot(published.share_token).dashboard_id == record.id

    query_count = len(connector.calls)
    rotated = service.rotate_publication(
        record.id,
        published.published_revision,
        "alice",
        share_expires_in_seconds=120,
    )
    with pytest.raises(LookupError):
        service.get_public_snapshot(published.share_token)
    assert service.get_public_snapshot(rotated.share_token).dashboard_id == record.id
    assert len(connector.calls) == query_count

    publications = service.list_publications(record.id, "alice")
    assert len(publications) == 2
    assert sum(item.active for item in publications) == 1
    assert service.revoke_publication(record.id, published.published_revision, "alice")
    with pytest.raises(LookupError):
        service.get_public_snapshot(rotated.share_token)

    expired_token = "expired-token"
    expired_hash = hashlib.sha256(expired_token.encode("utf-8")).hexdigest()
    dao.shares.append(
        DashboardShareEntity(
            id=99,
            dashboard_id=record.id,
            revision=published.published_revision,
            token_hash=expired_hash,
            created_by="alice",
            expires_at=datetime.now() - timedelta(seconds=1),
            gmt_created=datetime.now() - timedelta(minutes=1),
        )
    )
    with pytest.raises(LookupError):
        service.get_public_snapshot(expired_token)


def test_publish_is_blocked_when_any_widget_fails(service_fixture):
    service, _, _ = service_fixture
    payload = schema_payload()
    payload["widgets"][1]["query"]["sql"] = (
        "SELECT SUM(sales) AS runtime_fail FROM sales"
    )
    payload["widgets"][1]["query"]["output_fields"] = [
        {"name": "runtime_fail", "type": "number"}
    ]
    payload["widgets"][1]["encoding"] = {"x": "runtime_fail", "y": "runtime_fail"}
    # The modified query no longer matches its frozen-data binding. Keep it
    # absent so schema creation can exercise the live failure; publication
    # must still fail closed rather than expose a misleading interactive page.
    payload["widgets"][1].pop("publication", None)
    record = service.create_dashboard(
        DashboardCreateRequest(schema=DashboardSchemaV1.model_validate(payload)),
        "alice",
    )
    with pytest.raises(DashboardPublishValidationError):
        service.publish_dashboard(record.id, 1, {}, "alice")


def test_publish_rejects_an_oversized_immutable_snapshot(service_fixture, monkeypatch):
    service, _, _ = service_fixture
    record = service.create_dashboard(
        DashboardCreateRequest(
            schema=DashboardSchemaV1.model_validate(schema_payload())
        ),
        "alice",
    )
    monkeypatch.setattr(dashboard_service_module, "MAX_PUBLISHED_SNAPSHOT_BYTES", 1)

    with pytest.raises(DashboardPublishValidationError) as exc_info:
        service.publish_dashboard(record.id, 1, {}, "alice")

    assert {issue.code for issue in exc_info.value.result.issues} == {
        "snapshot_too_large"
    }


def test_agent_planner_keeps_a_failed_widget_as_an_editable_draft(service_fixture):
    service, dao, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Agent retail dashboard",
            "business_theme": "Store performance",
            "metrics": ["total sales"],
            "dimensions": ["month"],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "How much did we sell?",
                    "metric": "total sales",
                },
                {
                    "id": "broken-trend",
                    "type": "line",
                    "title": "Broken trend",
                    "business_question": "Can an invalid field break the draft?",
                    "metric": "sales",
                    "dimensions": ["missing_dimension"],
                },
            ],
        }
    )
    query_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "total-sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                },
                {
                    "widget_id": "broken-trend",
                    "sql": "SELECT missing_dimension, SUM(sales) AS sales FROM sales",
                    "output_fields": [
                        {"name": "missing_dimension", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "encoding": {"x": "missing_dimension", "y": "sales"},
                },
            ]
        }
    )
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    record, results = asyncio.run(
        planner.create_draft(
            plan=plan,
            query_request=query_request,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-1",
            prompt="Build a retail dashboard",
            model_name="mock-model",
            event_callback=capture,
        )
    )

    assert record.id in dao.rows
    assert results["total-sales"].error is None
    assert results["broken-trend"].error is not None
    failed_widget = next(
        item for item in record.schema_payload.widgets if item.id == "broken-trend"
    )
    assert failed_widget.error is not None
    assert failed_widget.query.sql.startswith("SELECT missing_dimension")
    assert [event_type for event_type, _ in events][-1] == "dashboard.created"
    assert "dashboard.widget.validated" in {event_type for event_type, _ in events}
    assert "dashboard.widget.failed" in {event_type for event_type, _ in events}


@pytest.mark.parametrize(
    ("widget_type", "expected_points", "allowed"),
    [
        ("line", None, False),
        ("line", 0, False),
        ("table", None, False),
        ("table", 0, True),
    ],
)
def test_agent_planner_preserves_only_approved_empty_tables(
    service_fixture, widget_type, expected_points, allowed
):
    service, _, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Empty result dashboard",
            "business_theme": "Store performance",
            "metrics": ["sales"],
            "dimensions": ["month"],
            "widgets": [
                {
                    "id": "empty-trend",
                    "type": widget_type,
                    "title": "Empty trend",
                    "business_question": "How did sales change?",
                    "metric": "sales",
                    "dimensions": ["month"],
                    "expected_data_points": expected_points,
                }
            ],
        }
    )
    query_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "empty-trend",
                    "sql": (
                        "SELECT month, sales FROM sales WHERE 1 = 0 /* empty_result */"
                    ),
                    "output_fields": [
                        {"name": "month", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "encoding": {"x": "month", "y": "sales"},
                }
            ]
        }
    )
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    record, results = asyncio.run(
        planner.create_draft(
            plan=plan,
            query_request=query_request,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-empty",
            prompt="Build an empty dashboard",
            model_name="mock-model",
            event_callback=capture,
        )
    )

    result = results["empty-trend"]
    widget = record.schema_payload.widgets[0]
    assert result.row_count == 0
    if allowed:
        assert result.error is None
        assert widget.error is None
        assert "WHERE 1 = 0" in widget.query.sql
        assert widget.query.last_execution.status == "succeeded"
        assert "dashboard.widget.validated" in [event for event, _ in events]
        repaired, repaired_results = asyncio.run(
            planner.repair_draft(
                dashboard_id=record.id,
                plan=plan,
                query_request=query_request,
                owner_id="alice",
                event_callback=capture,
            )
        )
        assert repaired_results["empty-trend"].rows == []
        assert repaired.schema_payload.widgets[0].error is None
        return
    assert result.error is not None
    assert result.error.code == "planner_widget_empty_result"
    assert widget.error is not None
    assert "0 行" in widget.error.message
    assert widget.query.last_execution.status == "failed"
    event_types = [event_type for event_type, _ in events]
    assert "dashboard.widget.failed" in event_types
    assert "dashboard.widget.validated" not in event_types
    created_payload = next(
        payload for event_type, payload in events if event_type == "dashboard.created"
    )
    assert created_payload["validated_widgets"] == 0
    assert created_payload["failed_widgets"] == 1


def test_agent_planner_builds_schema_1_3_publication_binding_with_server_source(
    service_fixture,
):
    service, _, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Shareable retail dashboard",
            "business_theme": "Store performance",
            "metrics": ["total sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "stores",
                    "type": "multi_select",
                    "label": "Stores",
                    "field": "store",
                }
            ],
            "widgets": [
                {
                    "id": "store-sales",
                    "type": "bar",
                    "title": "Store sales",
                    "business_question": "Which stores sell the most?",
                    "metric": "total sales",
                    "dimensions": ["store"],
                }
            ],
        }
    )
    query_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "store-sales",
                    "sql": (
                        "SELECT store, SUM(sales) AS total_sales FROM sales "
                        "WHERE store IN (:store_ids) GROUP BY store"
                    ),
                    "filter_parameters": {"stores": "store_ids"},
                    "output_fields": [
                        {"name": "store", "type": "string"},
                        {"name": "total_sales", "type": "number"},
                    ],
                    "encoding": {"x": "store", "y": "total_sales"},
                    "publication": {
                        "query": {
                            "sql": "SELECT store, sales FROM sales",
                            "output_fields": [
                                {"name": "store", "type": "string"},
                                {"name": "sales", "type": "number"},
                            ],
                        },
                        "filter_fields": {"stores": "store"},
                        "group_by": ["store"],
                        "measures": [
                            {
                                "source_field": "sales",
                                "output_field": "total_sales",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["store", "total_sales"],
                    },
                }
            ]
        }
    )

    record, _ = asyncio.run(
        planner.create_draft(
            plan=plan,
            query_request=query_request,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-shareable",
            prompt="Build a shareable store dashboard",
            model_name="mock-model",
        )
    )

    widget = record.schema_payload.widgets[0]
    assert record.schema_payload.schema_version == "1.4"
    assert record.schema_payload.dashboard.theme.preset.value == "clarity"
    assert record.schema_payload.dashboard.theme.mode.value == "light"
    assert widget.publication is not None
    assert widget.publication.query.data_source_id == "walmart"
    assert widget.publication.query.filter_parameters == {}
    assert widget.publication.filter_fields["stores"] == "store"


def test_agent_planner_inserts_an_error_placeholder_for_a_missing_query(
    service_fixture,
):
    service, _, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Partial dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": [],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "How much did we sell?",
                    "metric": "sales",
                },
                {
                    "id": "details",
                    "type": "table",
                    "title": "Details",
                    "business_question": "Which rows contributed?",
                    "metric": "sales",
                },
            ],
        }
    )
    query_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "total-sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                }
            ]
        }
    )
    record, _ = asyncio.run(
        planner.create_draft(
            plan=plan,
            query_request=query_request,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-2",
            prompt="Build a partial dashboard",
            model_name="mock-model",
        )
    )
    details = next(
        item for item in record.schema_payload.widgets if item.id == "details"
    )
    assert details.error is not None
    assert details.error.code == "query_not_generated"
    assert details.encoding.columns == ["message"]


def test_agent_repairs_only_failed_widget_in_the_same_draft(service_fixture):
    service, dao, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Repairable dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["month"],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "How much did we sell?",
                    "metric": "sales",
                },
                {
                    "id": "sales-trend",
                    "type": "line",
                    "title": "Sales trend",
                    "business_question": "How did sales move?",
                    "metric": "sales",
                    "dimensions": ["month"],
                },
            ],
        }
    )
    first_queries = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "total-sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                },
                {
                    "widget_id": "sales-trend",
                    "sql": "SELECT missing_dimension, SUM(sales) AS sales FROM sales",
                    "output_fields": [
                        {"name": "missing_dimension", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "encoding": {"x": "missing_dimension", "y": "sales"},
                },
            ]
        }
    )
    created, _ = asyncio.run(
        planner.create_draft(
            plan=plan,
            query_request=first_queries,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-repair",
            prompt="Build and repair",
            model_name="mock-model",
        )
    )
    original_success_sql = next(
        item.query.sql
        for item in created.schema_payload.widgets
        if item.id == "total-sales"
    )
    assert next(
        item for item in created.schema_payload.widgets if item.id == "sales-trend"
    ).error

    repair_queries = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "sales-trend",
                    "sql": _MONTHLY_SALES_SQL,
                    "output_fields": [
                        {"name": "month", "type": "string"},
                        {"name": "sales", "type": "number"},
                    ],
                    "encoding": {"x": "month", "y": "sales"},
                }
            ]
        }
    )
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    repaired, results = asyncio.run(
        planner.repair_draft(
            dashboard_id=created.id,
            plan=plan,
            query_request=repair_queries,
            owner_id="alice",
            event_callback=capture,
        )
    )

    assert repaired.id == created.id
    assert repaired.current_revision == 2
    assert len(dao.rows) == 1
    assert results["sales-trend"].error is None
    assert all(item.error is None for item in repaired.schema_payload.widgets)
    assert (
        next(
            item.query.sql
            for item in repaired.schema_payload.widgets
            if item.id == "total-sales"
        )
        == original_success_sql
    )
    assert [event_type for event_type, _ in events][-1] == "dashboard.created"


def test_agent_repair_promotes_pending_filtered_plan_to_schema_1_3(
    service_fixture,
):
    service, _, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Filtered repair",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "store_filter",
                    "type": "multi_select",
                    "label": "Store",
                    "field": "store",
                    "default": [1],
                    "options": [{"label": "1", "value": 1}],
                }
            ],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "How much did we sell?",
                    "metric": "sales",
                }
            ],
        }
    )
    pending = asyncio.run(
        planner.create_plan_draft(
            plan=plan,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-filtered-repair",
            prompt="Build a filtered dashboard",
            model_name="mock-model",
            request_token="planning-turn",
        )
    )
    assert pending.schema_payload.schema_version == "1.4"

    repair_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "total-sales",
                    "sql": (
                        "SELECT SUM(sales) AS total_sales FROM sales "
                        "WHERE store IN (:store_ids)"
                    ),
                    "filter_parameters": {"store_filter": "store_ids"},
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                    "publication": {
                        "query": {
                            "sql": "SELECT store, sales FROM sales",
                            "output_fields": [
                                {"name": "store", "type": "integer"},
                                {"name": "sales", "type": "number"},
                            ],
                        },
                        "filter_fields": {"store_filter": "store"},
                        "group_by": [],
                        "measures": [
                            {
                                "source_field": "sales",
                                "output_field": "total_sales",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["total_sales"],
                    },
                }
            ]
        }
    )
    repaired, results = asyncio.run(
        planner.repair_draft(
            dashboard_id=pending.id,
            plan=plan,
            query_request=repair_request,
            owner_id="alice",
        )
    )

    assert repaired.schema_payload.schema_version == "1.4"
    assert repaired.schema_payload.widgets[0].publication is not None
    assert results["total-sales"].error is None
    assert (
        repaired.schema_payload.metadata.compatibility["agent_dashboard_workflow"][
            "status"
        ]
        == "generated"
    )
    from dbgpt_app.openapi.api_v1.dashboard.confirmation import record_generation_result

    confirmation_state = {
        "dashboard_generation": {
            "dashboard_id": pending.id,
            "current_revision": pending.current_revision,
        },
        "dashboard_confirmation_contract": {"widgets": [{"widget_id": "total-sales"}]},
    }
    record_generation_result(confirmation_state, repaired)
    assert confirmation_state["dashboard_generation"]["status"] == "completed"


def test_agent_plan_requires_a_later_confirmation_turn(service_fixture):
    service, dao, _ = service_fixture
    planner = DashboardPlannerService(service)
    plan = DashboardPlan.model_validate(
        {
            "title": "Confirm before SQL",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": [],
            "widgets": [
                {
                    "id": "total-sales",
                    "type": "kpi",
                    "title": "Total sales",
                    "business_question": "How much did we sell?",
                    "metric": "sales",
                }
            ],
        }
    )
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    pending = asyncio.run(
        planner.create_plan_draft(
            plan=plan,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-confirm",
            prompt="Build a retail dashboard",
            model_name="mock-model",
            request_token="turn-one",
            event_callback=capture,
        )
    )
    workflow = pending.schema_payload.metadata.compatibility["agent_dashboard_workflow"]
    assert workflow["status"] == "awaiting_confirmation"
    assert pending.schema_payload.widgets[0].error.code == "query_not_generated"
    assert events[-1][0] == "dashboard.plan.awaiting_confirmation"
    assert events[-1][1]["dashboard_id"] == pending.id

    queries = DashboardQueryDraftRequest.model_validate(
        {
            "dashboard_id": pending.id,
            "expected_revision": 1,
            "widgets": [
                {
                    "widget_id": "total-sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                }
            ],
        }
    )
    with pytest.raises(ValueError, match="later user turn"):
        asyncio.run(
            planner.complete_plan_draft(
                dashboard_id=pending.id,
                query_request=queries,
                owner_id="alice",
                request_token="turn-one",
            )
        )

    completed, results = asyncio.run(
        planner.complete_plan_draft(
            dashboard_id=pending.id,
            query_request=queries,
            owner_id="alice",
            request_token="turn-two",
            event_callback=capture,
        )
    )
    assert completed.id == pending.id
    assert completed.current_revision == 2
    assert len(dao.rows) == 1
    assert results["total-sales"].error is None
    generation_events = [
        payload
        for event_type, payload in events
        if event_type.startswith("dashboard.widget.")
        or event_type == "dashboard.created"
    ]
    assert generation_events
    assert all(payload["dashboard_id"] == pending.id for payload in generation_events)
    assert all(payload["source_turn_id"] == "turn-one" for payload in generation_events)
    assert (
        completed.schema_payload.metadata.compatibility["agent_dashboard_workflow"][
            "status"
        ]
        == "generated"
    )
    assert (
        completed.schema_payload.metric_context.metrics[0].definition_source.value
        == "user_confirmed"
    )


def test_agent_can_revise_a_pending_plan_without_creating_a_second_dashboard(
    service_fixture,
):
    service, dao, _ = service_fixture
    planner = DashboardPlannerService(service)
    first = DashboardPlan.model_validate(
        {
            "title": "First plan",
            "description": "Decision-ready retail plan",
            "business_theme": "Retail",
            "audience": "Regional operators",
            "decision_goal": "Choose the first region to intervene in",
            "analysis_logic": ["Assess status", "Locate the driver"],
            "layout_rationale": "Status first, diagnostics second",
            "filter_strategy": "No filters are needed for this executive view",
            "metrics": ["sales"],
            "filters": [
                {
                    "id": "region",
                    "type": "select",
                    "label": "Region",
                    "field": "region",
                    "default": None,
                    "options": [{"label": "North", "value": "north"}],
                }
            ],
            "widgets": [
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                }
            ],
        }
    )
    pending = asyncio.run(
        planner.create_plan_draft(
            plan=first,
            data_source_id="walmart",
            owner_id="alice",
            conversation_id="conv-revise",
            prompt="Build it",
            model_name="mock-model",
            request_token="turn-one",
        )
    )
    revised_plan = DashboardPlan.model_validate(
        {
            "title": "Revised plan",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "widgets": [
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                    "rationale": "Anchor the operating decision",
                    "layout": {"width": "quarter", "height": "compact"},
                }
            ],
        }
    )
    revised = asyncio.run(
        planner.revise_plan_draft(
            dashboard_id=pending.id,
            plan=revised_plan,
            expected_revision=1,
            owner_id="alice",
            request_token="turn-two",
            prompt="Rename it",
            model_name="mock-model",
        )
    )
    assert revised.id == pending.id
    assert revised.current_revision == 2
    assert revised.schema_payload.dashboard.title == "Revised plan"
    assert len(dao.rows) == 1
    stored_plan = revised.schema_payload.metadata.compatibility[
        "agent_dashboard_workflow"
    ]["plan"]
    assert stored_plan["audience"] == "Regional operators"
    assert stored_plan["decision_goal"] == "Choose the first region to intervene in"
    assert stored_plan["analysis_logic"] == ["Assess status", "Locate the driver"]
    assert stored_plan["layout_rationale"] == "Status first, diagnostics second"
    assert stored_plan["filter_strategy"] == (
        "No global filters are used in this revision; widgets show the full "
        "approved analysis scope."
    )
    assert stored_plan["widgets"][0]["rationale"] == "Anchor the operating decision"
    assert stored_plan["widgets"][0]["layout"] == {
        "width": "quarter",
        "height": "compact",
    }
    assert (
        revised.schema_payload.metadata.compatibility["agent_dashboard_workflow"][
            "planned_request_token"
        ]
        == "turn-two"
    )


@pytest.mark.asyncio
async def test_dashboard_tools_cannot_generate_sql_in_the_planning_turn(
    service_fixture,
):
    service, dao, connector = service_fixture
    planner = DashboardPlannerService(service)
    events = []

    async def capture(event_type, payload):
        events.append((event_type, payload))

    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-tool"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    plan_payload = {
        "title": "Tool plan",
        "business_theme": "Retail",
        "metrics": ["sales"],
        "dimensions": [],
        "filters": [],
        "widgets": [
            {
                "id": "sales",
                "type": "kpi",
                "title": "Sales",
                "business_question": "How much?",
                "metric": "sales",
                "dimensions": [],
            }
        ],
    }
    planned_result = json.loads(
        await planning_tools["plan_dashboard"](plan=json.dumps(plan_payload))
    )
    dashboard_id = planned_result["__dashboard_plan_draft__"]["dashboard_id"]
    query_payload = {
        "dashboard_id": dashboard_id,
        "expected_revision": 1,
        "widgets": [
            {
                "widget_id": "sales",
                "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                "output_fields": [{"name": "total_sales", "type": "number"}],
                "encoding": {"value": "total_sales"},
            }
        ],
    }
    blocked = json.loads(
        await planning_tools["create_dashboard_draft"](
            widget_queries=json.dumps(query_payload)
        )
    )
    assert "did not explicitly confirm" in blocked["chunks"][0]["content"]
    assert dao.rows[dashboard_id].current_revision == 1

    confirmation_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-tool"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    completed_result = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            widget_queries=json.dumps(query_payload)
        )
    )
    assert completed_result["__dashboard__"]["dashboard_id"] == dashboard_id
    assert dao.rows[dashboard_id].current_revision == 2
    assert any(event_type == "dashboard.created" for event_type, _ in events)


@pytest.mark.asyncio
async def test_dashboard_tool_stages_bounded_query_batches(service_fixture):
    service, dao, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    planning_state = {"conv_id": "conv-staged-tool"}
    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=planning_state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build three sales KPIs",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    widgets = [
        {
            "id": widget_id,
            "type": "kpi",
            "title": title,
            "business_question": question,
            "metric": "sales",
            "dimensions": [],
        }
        for widget_id, title, question in (
            ("sales-total", "Sales total", "How much?"),
            ("sales-average", "Sales average", "What is the average?"),
            ("sales-maximum", "Sales maximum", "What is the maximum?"),
        )
    ]
    planned = json.loads(
        await planning_tools["plan_dashboard"](
            plan=json.dumps(
                {
                    "title": "Staged generation",
                    "business_theme": "Retail",
                    "metrics": ["sales"],
                    "dimensions": [],
                    "filters": [],
                    "widgets": widgets,
                }
            )
        )
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]
    confirmation_state = {"conv_id": "conv-staged-tool"}
    confirmation_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=confirmation_state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }

    malformed = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries='{"widgets": [',
        )
    )
    assert "at most two" in malformed["chunks"][0]["content"]

    def query(widget_id, aggregate, output_name):
        return {
            "widget_id": widget_id,
            "sql": f"SELECT {aggregate}(sales) AS {output_name} FROM sales",
            "output_fields": [{"name": output_name, "type": "number"}],
            "encoding": {"value": output_name},
        }

    staged = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries={
                "widgets": [
                    query("sales-total", "SUM", "total_sales"),
                    query("sales-average", "AVG", "average_sales"),
                ]
            },
        )
    )
    assert "__dashboard__" not in staged
    assert staged["__dashboard_generation_staging__"]["missing_widget_ids"] == [
        "sales-maximum"
    ]
    assert dao.rows[dashboard_id].current_revision == 1

    completed = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries={
                "widgets": [query("sales-maximum", "MAX", "maximum_sales")]
            },
        )
    )
    assert completed["__dashboard__"]["dashboard_id"] == dashboard_id
    assert completed["__dashboard__"]["total_widgets"] == 3
    assert dao.rows[dashboard_id].current_revision == 2
    assert "dashboard_query_staging" not in confirmation_state


@pytest.mark.asyncio
async def test_dashboard_tool_accepts_legacy_draft_wrapper(service_fixture):
    service, _, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-draft-alias"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales KPI",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    planned = json.loads(
        await planning_tools["plan_dashboard"](
            plan=json.dumps(
                {
                    "title": "Sales KPI",
                    "business_theme": "Retail",
                    "metrics": ["sales"],
                    "dimensions": [],
                    "filters": [],
                    "widgets": [
                        {
                            "id": "sales",
                            "type": "kpi",
                            "title": "Sales",
                            "business_question": "How much?",
                            "metric": "sales",
                            "dimensions": [],
                        }
                    ],
                }
            )
        )
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]
    confirmation_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-draft-alias"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }

    completed = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            draft={
                "widgets": [
                    {
                        "widget_id": "sales",
                        "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                        "fields": [
                            {
                                "name": "total_sales",
                                "type": "number",
                                "encoding": {
                                    "role": "metric",
                                    "aggregation": "sum",
                                },
                            }
                        ],
                        "publication": {"type": "kpi", "title": "Sales"},
                    }
                ]
            },
        )
    )

    assert completed["__dashboard__"]["dashboard_id"] == dashboard_id
    saved = service.get_dashboard(dashboard_id, "alice")
    assert saved.schema_payload.widgets[0].encoding.value == "total_sales"
    assert saved.schema_payload.widgets[0].publication is None


@pytest.mark.asyncio
async def test_repair_tool_normalizes_real_model_wrapper_and_publication(
    service_fixture,
):
    service, _, connector = service_fixture
    planner = DashboardPlannerService(service)
    react_state = {"conv_id": "conv-repair-alias"}

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=react_state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a filtered KPI",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    planned = json.loads(
        await tools["plan_dashboard"](
            plan=json.dumps(
                {
                    "title": "Repair alias KPI",
                    "business_theme": "Retail",
                    "metrics": ["sales"],
                    "dimensions": ["store"],
                    "filters": [
                        {
                            "id": "store_filter",
                            "type": "multi_select",
                            "label": "Store",
                            "field": "store",
                            "default": [1],
                            "options": [{"label": "1", "value": 1}],
                        }
                    ],
                    "widgets": [
                        {
                            "id": "sales",
                            "type": "kpi",
                            "title": "Sales",
                            "business_question": "How much?",
                            "metric": "sales",
                            "dimensions": [],
                        }
                    ],
                }
            )
        )
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]
    repaired = json.loads(
        await tools["repair_dashboard_draft"](
            widget_queries={
                "schema_version": "1.3",
                "widgets": {
                    "sales": {
                        "sql": (
                            "SELECT SUM(sales) AS total_sales FROM sales "
                            "WHERE store IN (:store_ids)"
                        ),
                        "output_fields": {
                            "total_sales": "number",
                        },
                        "encoding": {"value": "total_sales"},
                        "publication": {
                            "query": {
                                "sql": "SELECT store, sales FROM sales",
                                "output_fields": {
                                    "store": "integer",
                                    "sales": "number",
                                },
                            },
                            "filter_fields": {"store_ids": "store"},
                            "measures": [
                                {
                                    "source_field": "sales",
                                    "output_field": "total_sales",
                                    "aggregation": "sum",
                                }
                            ],
                            "output_columns": ["total_sales"],
                        },
                    }
                },
            }
        )
    )

    assert repaired["__dashboard__"]["dashboard_id"] == dashboard_id
    assert repaired["__dashboard__"]["publishable"] is True
    saved = service.get_dashboard(dashboard_id, "alice")
    assert saved.schema_payload.schema_version == "1.4"
    widget = saved.schema_payload.widgets[0]
    assert widget.query.filter_parameters == {"store_filter": "store_ids"}
    assert widget.publication is not None
    assert widget.publication.filter_fields == {"store_filter": "store"}


@pytest.mark.asyncio
async def test_plan_tool_accepts_canonical_fields_without_plan_wrapper(
    service_fixture,
):
    service, _, connector = service_fixture

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-unwrapped-plan"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=DashboardPlannerService(service),
        )
    }
    result = json.loads(
        await tools["plan_dashboard"](
            title="Unwrapped plan",
            description="Model emitted the sole argument fields directly.",
            business_theme="Retail",
            metrics=["sales"],
            dimensions=[],
            filters=[],
            widgets=[
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                    "dimensions": [],
                }
            ],
        )
    )

    assert result["__dashboard_plan_draft__"]["status"] == "awaiting_confirmation"
    assert result["__dashboard_plan__"]["title"] == "Unwrapped plan"
    assert result["__dashboard_ref__"]["status"] == "awaiting_confirmation"
    assert result["__dashboard_ref__"]["plan"]["title"] == "Unwrapped plan"
    assert "[[confirm-dashboard:" in result["__dashboard_ref__"]["confirmation_prompt"]
    assert "expected revision 1" in result["__dashboard_ref__"]["confirmation_prompt"]


@pytest.mark.asyncio
async def test_plan_tool_returns_bounded_actionable_validation_feedback(
    service_fixture,
):
    service, _, connector = service_fixture

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-invalid-plan"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=DashboardPlannerService(service),
        )
    }
    result = json.loads(
        await tools["plan_dashboard"](
            theme="Retail",
            decision="Compare stores",
            metrics=[{"name": "sales"}],
            dimensions=[{"name": "store"}],
            filters=[{"name": "Store", "type": "multi"}],
            widgets=[{"id": "sales", "type": "histogram"}],
        )
    )
    content = result["chunks"][0]["content"]

    assert len(content) < 3000
    assert "Required shape" in content
    assert "call plan_dashboard again" in content
    assert "For further information" not in content


@pytest.mark.asyncio
async def test_confirmation_turn_preloads_the_authoritative_plan_contract(
    service_fixture,
):
    service, _, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    planning_state = {"conv_id": "conv-plan-contract"}
    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=planning_state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    plan_payload = {
        "title": "Authoritative plan",
        "business_theme": "Retail",
        "metrics": ["sales"],
        "dimensions": ["store"],
        "filters": [
            {
                "id": "store_filter",
                "type": "multi_select",
                "label": "Store",
                "field": "store",
                "options": [{"label": "Store 1", "value": 1}],
            }
        ],
        "widgets": [
            {
                "id": "sales_by_store",
                "type": "bar",
                "title": "Sales by store",
                "business_question": "How do stores compare?",
                "metric": "sales",
                "dimensions": ["store"],
            }
        ],
    }
    planned = json.loads(
        await planning_tools["plan_dashboard"](plan=json.dumps(plan_payload))
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]

    confirmation_state = {"conv_id": "conv-plan-contract"}
    make_dashboard_planner_tools(
        react_state=confirmation_state,
        database_connector=connector,
        database_name="walmart",
        owner_id="alice",
        user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
        model_name="mock-model",
        stream_callback=capture,
        planner_service=planner,
    )

    assert confirmation_state["dashboard_record_id"] == dashboard_id
    assert confirmation_state["dashboard_plan"]["title"] == plan_payload["title"]
    stored_widget = confirmation_state["dashboard_plan"]["widgets"][0]
    for key, value in plan_payload["widgets"][0].items():
        assert stored_widget[key] == value
    assert stored_widget["analysis_level"] == 3
    assert stored_widget["rationale"] == ""
    assert stored_widget["layout"] is None
    assert confirmation_state["dashboard_confirmation_contract"] == {
        "dashboard_id": dashboard_id,
        "expected_revision": 1,
        "widgets": [
            {
                "widget_id": "sales_by_store",
                "type": "bar",
                "title": "Sales by store",
                "metric": "sales",
                "dimensions": ["store"],
            }
        ],
        "filters": [
            {
                "filter_id": "store_filter",
                "type": "multi_select",
                "field": "store",
            }
        ],
    }


def test_planner_requires_planned_filters_to_bind_real_sql_parameters():
    plan = DashboardPlan.model_validate(
        {
            "title": "Filtered sales",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "store_filter",
                    "type": "multi_select",
                    "label": "Store",
                    "field": "store",
                    "options": [{"label": "Store 1", "value": 1}],
                }
            ],
            "widgets": [
                {
                    "id": "sales_by_store",
                    "type": "bar",
                    "title": "Sales by store",
                    "business_question": "How do stores compare?",
                    "metric": "sales",
                    "dimensions": ["store"],
                }
            ],
        }
    )
    unbound = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "sales_by_store",
                    "sql": (
                        "SELECT store, SUM(sales) AS total FROM sales GROUP BY store"
                    ),
                    "output_fields": [
                        {"name": "store", "type": "integer"},
                        {"name": "total", "type": "number"},
                    ],
                    "encoding": {"x": "store", "y": "total"},
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="store_filter"):
        DashboardPlannerService._validate_filter_bindings(plan, unbound)

    missing_placeholder = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "sales_by_store",
                    "sql": (
                        "SELECT store, SUM(sales) AS total FROM sales GROUP BY store"
                    ),
                    "filter_parameters": {"store_filter": "store_ids"},
                    "output_fields": [
                        {"name": "store", "type": "integer"},
                        {"name": "total", "type": "number"},
                    ],
                    "encoding": {"x": "store", "y": "total"},
                }
            ]
        }
    )
    with pytest.raises(ValueError, match=":store_ids"):
        DashboardPlannerService._validate_filter_bindings(plan, missing_placeholder)


def test_planner_rejects_filtered_generation_without_publication_contract():
    plan = DashboardPlan.model_validate(
        {
            "title": "Filtered dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "stores",
                    "type": "multi_select",
                    "label": "Stores",
                    "field": "store",
                    "default": [],
                    "options": [],
                }
            ],
            "widgets": [
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                    "dimensions": [],
                }
            ],
        }
    )
    query_request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "sales",
                    "sql": (
                        "SELECT SUM(sales) AS sales FROM sales WHERE store IN (:stores)"
                    ),
                    "filter_parameters": {"stores": "stores"},
                    "output_fields": [{"name": "sales", "type": "number"}],
                    "encoding": {"value": "sales"},
                }
            ]
        }
    )

    with pytest.raises(DashboardSchemaValidationError) as exc_info:
        DashboardPlannerService._validate_publication_drafts(plan, query_request)

    assert [issue.code for issue in exc_info.value.issues] == [
        "publication_binding_required"
    ]
    assert exc_info.value.issues[0].path == "widgets.sales.publication"


def test_generated_filter_contract_requires_real_fields_and_legal_defaults():
    payload = {
        "title": "Filtered sales",
        "business_theme": "Retail",
        "metrics": ["sales"],
        "dimensions": ["store"],
        "filters": [
            {
                "id": "store_filter",
                "type": "multi_select",
                "label": "Store",
                "field": "missing_store",
                "default": [2],
                "options": [{"label": "Store 1", "value": 1}],
            }
        ],
        "widgets": [
            {
                "id": "sales_by_store",
                "type": "bar",
                "title": "Sales by store",
                "business_question": "How do stores compare?",
                "metric": "sales",
                "dimensions": ["store"],
            }
        ],
    }
    plan = DashboardPlan.model_validate(payload)
    with pytest.raises(ValueError, match="unknown data field"):
        _validate_generated_filter_contract(plan, {"store", "sales"})

    payload["filters"][0]["field"] = "store"
    plan = DashboardPlan.model_validate(payload)
    with pytest.raises(ValueError, match="not present"):
        _validate_generated_filter_contract(plan, {"store", "sales"})

    payload["filters"][0]["default"] = [1]
    _validate_generated_filter_contract(
        DashboardPlan.model_validate(payload), {"store", "sales"}
    )


def test_model_query_payload_normalizes_unambiguous_agent_aliases():
    plan = DashboardPlan.model_validate(
        {
            "title": "Olist",
            "business_theme": "Commerce",
            "metrics": ["payment"],
            "dimensions": ["state"],
            "filters": [
                {
                    "id": "filter_customer_state",
                    "type": "multi_select",
                    "label": "State",
                    "field": "customer_state",
                    "default": ["SP"],
                    "options": [{"label": "SP", "value": "SP"}],
                }
            ],
            "widgets": [
                {
                    "id": "payment",
                    "type": "kpi",
                    "title": "Payment",
                    "business_question": "How much?",
                    "metric": "payment",
                    "dimensions": [],
                }
            ],
        }
    )
    normalized = _normalize_model_query_payload(
        {
            "schema_version": "1.3",
            "widgets": [
                {
                    "widget_id": "payment",
                    "sql": (
                        "SELECT SUM(payment) AS payment FROM sales "
                        "WHERE customer_state IN (:customer_states)"
                    ),
                    "filter_parameters": {
                        "customer_states": {
                            "type": "list",
                            "field": "customer_state",
                        }
                    },
                    "output_fields": [{"name": "payment", "type": "float"}],
                    "encoding": {"value": "payment"},
                    "publication": {
                        "query": {
                            "sql": "SELECT customer_state, payment FROM sales",
                            "output_fields": [
                                {"name": "customer_state", "type": "str"},
                                {"name": "payment", "type": "decimal"},
                            ],
                        }
                    },
                }
            ],
        },
        plan,
    )

    assert "schema_version" not in normalized
    widget = normalized["widgets"][0]
    assert widget["filter_parameters"] == {"filter_customer_state": "customer_states"}
    assert widget["output_fields"][0]["type"] == "number"
    assert [
        item["type"] for item in widget["publication"]["query"]["output_fields"]
    ] == ["string", "number"]


def test_model_query_payload_normalizes_global_parameters_and_publication_aliases():
    plan = DashboardPlan.model_validate(
        {
            "title": "Filtered dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "store_filter",
                    "type": "multi_select",
                    "label": "Store",
                    "field": "store",
                    "default": [1],
                    "options": [{"label": "1", "value": 1}],
                }
            ],
            "widgets": [
                {
                    "id": "sales",
                    "type": "bar",
                    "title": "Sales",
                    "business_question": "Which store sells most?",
                    "metric": "sales",
                    "dimensions": ["store"],
                }
            ],
        }
    )
    normalized = _normalize_model_query_payload(
        {
            "filter_parameters": {"store_filter": "store_ids"},
            "widget_queries": {
                "sales": {
                    "sql": (
                        "SELECT store, SUM(sales) AS sales FROM sales "
                        "WHERE store IN (:store_ids) GROUP BY store"
                    ),
                    "fields": [
                        {
                            "name": "store",
                            "type": "str",
                            "encoding": {"channel": "x"},
                        },
                        {
                            "name": "sales",
                            "type": "float",
                            "encoding": {"channel": "y"},
                        },
                    ],
                    "publication": {
                        "query": {
                            "sql": "SELECT store, sales FROM sales",
                            "fields": {"store": "str", "sales": "float"},
                        },
                        "filter_fields": {"store": "store_filter"},
                        "group_by": ["store"],
                        "measures": [
                            {
                                "source_field": "sales",
                                "output_field": "sales",
                                "aggregation": "sum",
                            }
                        ],
                        "sort": [{"field": "sales", "order": "desc"}],
                    },
                }
            },
        },
        plan,
    )

    assert "filter_parameters" not in normalized
    widget = normalized["widgets"][0]
    assert widget["filter_parameters"] == {"store_filter": "store_ids"}
    assert widget["encoding"] == {"x": "store", "y": "sales"}
    assert widget["publication"]["filter_fields"] == {"store_filter": "store"}
    assert widget["publication"]["output_columns"] == ["store", "sales"]
    assert widget["publication"]["sort"] == [
        {"field": "sales", "direction": "descending"}
    ]
    DashboardQueryDraftRequest.model_validate(normalized)


def test_model_query_payload_recovers_repair_filter_mappings_from_sql():
    plan = DashboardPlan.model_validate(
        {
            "title": "Repair aliases",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": [],
            "filters": [
                {
                    "id": "store_filter",
                    "type": "multi_select",
                    "label": "Store",
                    "field": "store",
                    "default": [1],
                    "options": [{"label": "1", "value": 1}],
                }
            ],
            "widgets": [
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                }
            ],
        }
    )
    normalized = _normalize_model_query_payload(
        {
            "schema_version": "1.3",
            "widgets": [
                {
                    "widget_id": "sales",
                    "sql": (
                        "SELECT SUM(sales) AS total_sales FROM sales "
                        "WHERE store IN (:store_ids)"
                    ),
                    "output_fields": [{"name": "total_sales", "type": "number"}],
                    "encoding": {"value": "total_sales"},
                    "publication": {
                        "query": {
                            "sql": "SELECT store, sales FROM sales",
                            "output_fields": [
                                {"name": "store", "type": "integer"},
                                {"name": "sales", "type": "number"},
                            ],
                        },
                        "filter_fields": {"store_ids": "store"},
                        "measures": [
                            {
                                "source_field": "sales",
                                "output_field": "total_sales",
                                "aggregation": "sum",
                            }
                        ],
                        "output_columns": ["total_sales"],
                    },
                }
            ],
        },
        plan,
    )

    assert "schema_version" not in normalized
    widget = normalized["widgets"][0]
    assert widget["filter_parameters"] == {"store_filter": "store_ids"}
    assert widget["publication"]["filter_fields"] == {"store_filter": "store"}
    DashboardQueryDraftRequest.model_validate(normalized)


def test_model_query_payload_infers_roles_and_ignores_presentation_publication():
    plan = DashboardPlan.model_validate(
        {
            "title": "Role-encoded dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": [],
            "filters": [],
            "widgets": [
                {
                    "id": "sales",
                    "type": "kpi",
                    "title": "Sales",
                    "business_question": "How much?",
                    "metric": "sales",
                    "dimensions": [],
                }
            ],
        }
    )

    normalized = _normalize_model_query_payload(
        {
            "widgets": [
                {
                    "widget_id": "sales",
                    "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                    "fields": [
                        {
                            "name": "total_sales",
                            "type": "number",
                            "encoding": {"role": "metric", "aggregation": "sum"},
                        }
                    ],
                    "publication": {"type": "kpi", "title": "Sales"},
                }
            ]
        },
        plan,
    )

    assert normalized["widgets"][0]["encoding"] == {"value": "total_sales"}
    assert normalized["widgets"][0]["publication"] is None
    DashboardQueryDraftRequest.model_validate(normalized)


def test_verified_olist_contract_repairs_model_queries_and_publication():
    filters = [
        {
            "id": "filter_purchase_year",
            "type": "multi_select",
            "label": "购买年份",
            "field": "order_purchase_timestamp",
            "default": [2018],
            "options": [{"label": "2018", "value": 2018}],
        },
        {
            "id": "filter_customer_state",
            "type": "multi_select",
            "label": "客户州",
            "field": "customer_state",
            "default": ["SP"],
            "options": [{"label": "SP", "value": "SP"}],
        },
        {
            "id": "filter_order_status",
            "type": "select",
            "label": "订单状态",
            "field": "order_status",
            "default": "delivered",
            "options": [{"label": "已送达", "value": "delivered"}],
        },
    ]
    widget_specs = [
        ("w_payment", "kpi", "支付总额"),
        ("w_delivery", "kpi", "已送达率"),
        ("w_month", "line", "月度支付趋势"),
        ("w_category", "bar", "品类成交额"),
        ("w_review", "bar", "评分分布"),
        ("w_detail", "table", "订单明细"),
    ]
    plan = DashboardPlan.model_validate(
        {
            "title": "Olist",
            "business_theme": "Commerce",
            "metrics": ["payment"],
            "dimensions": ["state"],
            "filters": filters,
            "widgets": [
                {
                    "id": widget_id,
                    "type": widget_type,
                    "title": title,
                    "business_question": title,
                    "metric": "payment",
                    "dimensions": [],
                }
                for widget_id, widget_type, title in widget_specs
            ],
        }
    )
    request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": widget_id,
                    "sql": "SELECT 1 AS value",
                    "output_fields": [{"name": "value", "type": "number"}],
                    "encoding": {"value": "value"},
                }
                for widget_id, _, _ in widget_specs
            ]
        }
    )

    effective_plan, effective_request, repaired = (
        DashboardPlannerService._repair_generation_contract(
            plan, request, "olist_ecommerce_demo"
        )
    )

    assert repaired == [item[0] for item in widget_specs]
    year_filter = next(
        item for item in effective_plan.filters if item.id == "filter_purchase_year"
    )
    assert year_filter.field == "purchase_year"
    assert year_filter.default == ["2016", "2017", "2018"]
    assert all(item.publication is not None for item in effective_request.widgets)
    assert all(
        set(item.filter_parameters)
        == {
            "filter_purchase_year",
            "filter_customer_state",
            "filter_order_status",
        }
        for item in effective_request.widgets
    )
    assert all(
        set(item.publication.filter_fields)
        == {
            "filter_purchase_year",
            "filter_customer_state",
            "filter_order_status",
        }
        for item in effective_request.widgets
        if item.publication is not None
    )


def test_explicit_standard_olist_prompt_is_constrained_to_verified_plan():
    proposed = DashboardPlan.model_validate(
        {
            "title": "Model expanded plan",
            "business_theme": "Commerce",
            "metrics": ["orders"],
            "dimensions": [],
            "filters": [],
            "widgets": [
                {
                    "id": "extra",
                    "type": "kpi",
                    "title": "An unrequested KPI",
                    "business_question": "Extra?",
                    "metric": "orders",
                    "dimensions": [],
                }
            ],
        }
    )
    prompt = (
        "请生成看板，包含购买年份、客户州、订单状态筛选器，并展示支付总额、"
        "已送达率、月度趋势、品类成交额、评价分布和订单核对表。"
    )

    normalized, used = normalize_verified_olist_plan(
        proposed, prompt, "olist_ecommerce_demo"
    )

    assert used is True
    assert [item.id for item in normalized.filters] == [
        "purchase-years",
        "customer-states",
        "order-status",
    ]
    assert [item.id for item in normalized.widgets] == [
        "payment-total",
        "delivered-rate",
        "monthly-payments",
        "category-revenue",
        "review-distribution",
        "order-detail",
    ]
    assert normalized.filters[0].field == "order_purchase_timestamp"


def test_generation_auto_repairs_a_parameter_free_static_widget_publication():
    plan = DashboardPlan.model_validate(
        {
            "title": "Mixed dashboard",
            "business_theme": "Retail",
            "metrics": ["sales"],
            "dimensions": ["store"],
            "filters": [
                {
                    "id": "stores",
                    "type": "multi_select",
                    "label": "Stores",
                    "field": "store",
                    "default": [1],
                    "options": [{"label": "1", "value": 1}],
                }
            ],
            "widgets": [
                {
                    "id": "headline",
                    "type": "kpi",
                    "title": "Headline",
                    "business_question": "What is the fixed benchmark?",
                    "metric": "sales",
                    "dimensions": [],
                }
            ],
        }
    )
    request = DashboardQueryDraftRequest.model_validate(
        {
            "widgets": [
                {
                    "widget_id": "headline",
                    "sql": "SELECT 42 AS sales",
                    "output_fields": [{"name": "sales", "type": "number"}],
                    "encoding": {"value": "sales"},
                }
            ]
        }
    )

    _, repaired_request, repaired = DashboardPlannerService._repair_generation_contract(
        plan, request, "walmart"
    )

    assert repaired == ["headline"]
    publication = repaired_request.widgets[0].publication
    assert publication is not None
    assert publication.row_mode is True
    assert publication.query.sql == "SELECT 42 AS sales"
    assert publication.output_columns == ["sales"]


def test_draft_validation_feedback_is_bounded_and_explains_contract():
    with pytest.raises(ValidationError) as exc_info:
        DashboardQueryDraftRequest.model_validate(
            {
                "widgets": [
                    {
                        "widget_id": "payment",
                        "sql": "SELECT 1 AS payment WHERE state IN (:states)",
                        "filter_parameters": {
                            "states": {"type": "list", "field": "state"}
                        },
                        "output_fields": [{"name": "payment", "type": "float"}],
                        "encoding": {"value": "payment"},
                    }
                ]
            }
        )

    message = _draft_validation_message(exc_info.value)
    assert len(message) < 3000
    assert "filter_parameters must map each Dashboard filter id" in message
    assert "output field types are" in message
    assert "For further information" not in message


@pytest.mark.asyncio
async def test_dashboard_tool_accepts_identity_and_normalizes_table_encoding(
    service_fixture,
):
    """Mirror the argument shape produced by the real DeepSeek tool call."""

    service, dao, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-real-shape"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a comparison table",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    plan_payload = {
        "title": "Store comparison",
        "business_theme": "Retail",
        "metrics": ["sales"],
        "dimensions": ["store"],
        "filters": [],
        "widgets": [
            {
                "id": "store-comparison",
                "type": "table",
                "title": "Store comparison",
                "business_question": "How do stores compare?",
                "metric": "sales",
                "dimensions": ["store"],
            }
        ],
    }
    planned = json.loads(
        await planning_tools["plan_dashboard"](plan=json.dumps(plan_payload))
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]

    confirmation_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-real-shape"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    # The real model supplied identity as top-level tool arguments and kept only
    # the widgets array inside widget_queries. It also supplied an irrelevant
    # value encoding for a table; the server should canonicalize that safely.
    query_payload = {
        "widgets": [
            {
                "widget_id": "store-comparison",
                "sql": (
                    "SELECT store, SUM(sales) AS total_sales FROM sales GROUP BY store"
                ),
                "output_fields": [
                    {"name": "store", "type": "integer"},
                    {"name": "total_sales", "type": "number"},
                ],
                "encoding": {
                    "value": "total_sales,avg_unemployment",
                    "columns": ["store", "total_sales"],
                },
            }
        ]
    }
    completed = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries=json.dumps(query_payload),
        )
    )

    assert completed["__dashboard__"]["dashboard_id"] == dashboard_id
    saved = service.get_dashboard(dashboard_id, "alice")
    assert saved.current_revision == 2
    assert saved.schema_payload.widgets[0].encoding.columns == [
        "store",
        "total_sales",
    ]
    assert saved.schema_payload.widgets[0].encoding.value is None
    assert len(dao.rows) == 1


@pytest.mark.asyncio
async def test_dashboard_tool_normalizes_query_map_and_infers_filter_bindings(
    service_fixture,
):
    """Accept the bounded alternate shape observed from the real model.

    DeepSeek encoded ``widget_queries`` as ``{widget_id: query}``.  The query
    itself was safe and already contained named parameters, so the tool should
    normalize the wrapper and link those existing placeholders to the persisted
    filters. SQL text and filter values must never be interpolated.
    """

    service, dao, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-query-map"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a filtered sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    plan_payload = {
        "title": "Filtered sales",
        "description": "",
        "business_theme": "retail",
        "metrics": ["sales"],
        "dimensions": ["store"],
        "filters": [
            {
                "id": "date_range",
                "type": "date_range",
                "label": "Date range",
                "field": "date",
                "default": ["2024-01-01", "2024-12-31"],
                "options": [],
            },
            {
                "id": "store_multi",
                "type": "multi_select",
                "label": "Stores",
                "field": "store",
                "default": None,
                "options": [{"label": "1", "value": "1"}],
            },
            {
                "id": "holiday_select",
                "type": "select",
                "label": "Holiday",
                "field": "holiday_flag",
                "default": None,
                "options": [{"label": "No", "value": "0"}],
            },
        ],
        "widgets": [
            {
                "id": "sales",
                "type": "kpi",
                "title": "Sales",
                "business_question": "What are total sales?",
                "metric": "sales",
                "dimensions": [],
            }
        ],
    }
    planned = json.loads(
        await planning_tools["plan_dashboard"](plan=json.dumps(plan_payload))
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]

    confirmation_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-query-map"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    model_query_map = {
        "sales": {
            "sql": (
                "SELECT SUM(sales) AS total_sales FROM sales "
                "WHERE (:start_date IS NULL OR date >= :start_date) "
                "AND (:end_date IS NULL OR date <= :end_date) "
                "AND (:store_ids IS NULL OR store IN (:store_ids)) "
                "AND (:holiday_flag IS NULL OR holiday = :holiday_flag)"
            ),
            "output_fields": {"total_sales": "number"},
            "encoding": {"value": "total_sales"},
            "publication": {
                "query": {
                    "sql": (
                        "SELECT date, store, holiday AS holiday_flag, sales FROM sales"
                    ),
                    "output_fields": {
                        "date": "date",
                        "store": "number",
                        "holiday_flag": "string",
                        "sales": "number",
                    },
                },
                "filter_fields": {
                    "date_range": "date",
                    "store_multi": "store",
                    "holiday_select": "holiday_flag",
                },
                "group_by": [],
                "measures": [
                    {
                        "source_field": "sales",
                        "output_field": "total_sales",
                        "aggregation": "sum",
                    }
                ],
                "output_columns": ["total_sales"],
                "sort": [],
                "max_output_rows": 100,
            },
        }
    }
    completed = json.loads(
        await confirmation_tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries=json.dumps(model_query_map),
        )
    )

    assert completed["__dashboard__"]["dashboard_id"] == dashboard_id
    saved = service.get_dashboard(dashboard_id, "alice")
    bindings = saved.schema_payload.widgets[0].query.filter_parameters
    assert bindings["date_range"].start_parameter == "start_date"
    assert bindings["date_range"].end_parameter == "end_date"
    assert bindings["store_multi"] == "store_ids"
    assert bindings["holiday_select"] == "holiday_flag"
    assert saved.schema_payload.widgets[0].query.output_fields[0].name == "total_sales"
    assert len(dao.rows) == 1


@pytest.mark.asyncio
async def test_dashboard_tool_returns_actionable_schema_issue_details(
    service_fixture, monkeypatch
):
    service, _, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    async def fail_with_schema_issue(**_kwargs):
        from dbgpt_app.openapi.api_v1.dashboard.schemas import ValidationIssue

        raise DashboardSchemaValidationError(
            [
                ValidationIssue(
                    path="widgets.0.encoding",
                    code="unknown_encoding_field",
                    message="Encoding field is not declared.",
                )
            ]
        )

    planning_tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-schema-error"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt="Build a sales dashboard",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    planned = json.loads(
        await planning_tools["plan_dashboard"](
            plan=json.dumps(
                {
                    "title": "Schema error plan",
                    "business_theme": "Retail",
                    "metrics": ["sales"],
                    "dimensions": [],
                    "filters": [],
                    "widgets": [
                        {
                            "id": "sales",
                            "type": "kpi",
                            "title": "Sales",
                            "business_question": "How much?",
                            "metric": "sales",
                            "dimensions": [],
                        }
                    ],
                }
            )
        )
    )
    dashboard_id = planned["__dashboard_plan_draft__"]["dashboard_id"]
    monkeypatch.setattr(planner, "complete_plan_draft", fail_with_schema_issue)
    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "conv-schema-error"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    result = json.loads(
        await tools["create_dashboard_draft"](
            dashboard_id=dashboard_id,
            expected_revision=1,
            widget_queries=json.dumps(
                {
                    "widgets": [
                        {
                            "widget_id": "sales",
                            "sql": "SELECT SUM(sales) AS total_sales FROM sales",
                            "output_fields": [
                                {"name": "total_sales", "type": "number"}
                            ],
                            "encoding": {"value": "total_sales"},
                        }
                    ]
                }
            ),
        )
    )

    content = result["chunks"][0]["content"]
    assert "widgets.0.encoding" in content
    assert "unknown_encoding_field" in content
    assert "Encoding field is not declared" in content
    assert result["__dashboard_repair_required__"]["status"] == "repair_required"
    assert result["__dashboard_repair_required__"]["component_ids"] == ["0"]


def test_read_only_annotation_turn_does_not_expose_dashboard_write_tools(
    service_fixture,
):
    service, _, connector = service_fixture
    planner = DashboardPlannerService(service)

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name
        for item in make_dashboard_planner_tools(
            react_state={"conv_id": "read-only-anomaly"},
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=(
                "[[dashboard-annotation:dashboard-1:annotation-1]] "
                "[异常分析] 收入趋势\n本批次没有修改类批注，不要修改看板。"
            ),
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }

    assert tools == {"load_dashboard_draft", "resolve_dashboard_reference"}


@pytest.mark.asyncio
async def test_existing_dashboard_tools_load_resolve_and_never_guess_or_duplicate(
    service_fixture,
):
    service, dao, connector = service_fixture
    existing = create_record(service)
    planner = DashboardPlannerService(service)
    state = {"conv_id": "existing-dashboard-edit"}

    async def capture(_event_type, _payload):
        return None

    prompt = f"继续修改已有看板 {existing.id}：右边那个改一下"
    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=prompt,
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }

    rejected = json.loads(
        await tools["modify_dashboard_draft"](
            dashboard_id=existing.id,
            expected_revision=existing.current_revision,
            operations=json.dumps(
                [{"op": "replace", "path": "/widgets/1/title", "value": "新标题"}]
            ),
        )
    )
    assert "call load_dashboard_draft" in rejected["chunks"][0]["content"]

    loaded = json.loads(await tools["load_dashboard_draft"](existing.id))
    assert loaded["__dashboard_draft__"]["dashboard_id"] == existing.id
    assert loaded["__dashboard_draft__"]["expected_revision"] == 1
    assert loaded["__dashboard_draft__"]["schema"]["widgets"][1]["id"] == "sales-trend"
    assert len(dao.rows) == 1
    assert service.get_dashboard(existing.id, "alice").current_revision == 1

    resolution = json.loads(
        await tools["resolve_dashboard_reference"](
            dashboard_id=existing.id,
            reference="右边那个",
        )
    )
    resolved = resolution["__dashboard_target_resolution__"]
    assert resolved["status"] == "resolved"
    assert resolved["target"]["widget_id"] == "sales-trend"

    wrong_scope = json.loads(
        await tools["modify_dashboard_draft"](
            dashboard_id=existing.id,
            expected_revision=1,
            operations=json.dumps(
                [
                    {
                        "op": "replace",
                        "path": "/widgets/0/title",
                        "value": "不应修改",
                    }
                ]
            ),
        )
    )
    assert (
        "may change only the uniquely resolved widget"
        in (wrong_scope["chunks"][0]["content"])
    )
    assert service.get_dashboard(existing.id, "alice").current_revision == 1

    duplicate_plan = json.loads(
        await tools["plan_dashboard"](
            plan=json.dumps(
                {
                    "title": "不应创建",
                    "business_theme": "重复",
                    "metrics": ["sales"],
                    "widgets": [
                        {
                            "id": "sales",
                            "type": "kpi",
                            "title": "Sales",
                            "business_question": "How much?",
                            "metric": "sales",
                            "dimensions": [],
                        }
                    ],
                }
            )
        )
    )
    assert "do not create a duplicate" in duplicate_plan["chunks"][0]["content"]
    assert len(dao.rows) == 1


@pytest.mark.asyncio
async def test_existing_dashboard_tool_requires_clarification_for_this_chart(
    service_fixture,
):
    service, _, connector = service_fixture
    existing = create_record(service)
    planner = DashboardPlannerService(service)
    state = {"conv_id": "ambiguous-dashboard-edit"}

    async def capture(_event_type, _payload):
        return None

    tools = {
        item._tool.name: item
        for item in make_dashboard_planner_tools(
            react_state=state,
            database_connector=connector,
            database_name="walmart",
            owner_id="alice",
            user_prompt=f"继续修改看板 {existing.id}：这个图太挤了",
            model_name="mock-model",
            stream_callback=capture,
            planner_service=planner,
        )
    }
    await tools["load_dashboard_draft"](existing.id)
    resolution = json.loads(
        await tools["resolve_dashboard_reference"](
            dashboard_id=existing.id,
            reference="这个图太挤了",
        )
    )

    assert (
        resolution["__dashboard_target_resolution__"]["status"] == "needs_clarification"
    )
    assert resolution["__dashboard_target_resolution__"]["question"]
    rejected = json.loads(
        await tools["modify_dashboard_draft"](
            dashboard_id=existing.id,
            expected_revision=1,
            operations=json.dumps(
                [{"op": "replace", "path": "/widgets/0/title", "value": "新标题"}]
            ),
        )
    )
    assert "not uniquely resolved" in rejected["chunks"][0]["content"]
    assert service.get_dashboard(existing.id, "alice").current_revision == 1
