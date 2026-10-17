"""Publishing must authorize every queried source before executing any SQL."""

# Imported pytest fixtures are injected as arguments below.
# ruff: noqa: F811
import json
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.access import DashboardAuthorizationService
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardAccessDao,
    DashboardAccessDeniedError,
    DashboardAuditDao,
    DashboardDao,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardSchemaV1,
    DashboardValidateRequest,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService

from .test_service import FakeConnector, create_record, service_fixture  # noqa: F401


@pytest.mark.parametrize(
    "source_kind", ["widget", "publication", "publication_federation"]
)
def test_publish_denies_inaccessible_sources_before_validation_or_query(
    service_fixture, monkeypatch, source_kind
):
    """An owner may publish the dashboard but still lack source query access."""
    service, dao, connector = service_fixture
    record = create_record(service)
    payload = record.schema_payload.model_dump(mode="json", by_alias=True)
    query = (
        payload["widgets"][0]["query"]
        if source_kind == "widget"
        else payload["widgets"][0]["publication"]["query"]
    )
    if source_kind == "publication_federation":
        query["federation"] = {
            "mode": "union_all",
            "sources": [
                {
                    "alias": alias,
                    "data_source_id": source,
                    "sql": "SELECT sales FROM sales",
                    "column_mapping": {"sales": "sales"},
                }
                for alias, source in [("allowed", "walmart"), ("restricted", "payroll")]
            ],
        }
        query["sql"] = None
    else:
        query["data_source_id"] = "payroll"
    # Model an already saved schema after its owner's access policy changed.
    DashboardSchemaV1.model_validate(payload)
    dao.rows[record.id].schema_json = json.dumps(payload)
    service.authorization = DashboardAuthorizationService(
        dashboard_dao=dao,
        access_dao=Mock(),
        audit_dao=Mock(),
        data_source_authorizer=lambda actor, source: source == "walmart",
        require_data_source_authorizer=True,
    )
    validation = Mock(
        side_effect=AssertionError("Validation must not run before authorization")
    )
    monkeypatch.setattr(service, "validate_schema", validation)
    connector.calls.clear()

    with pytest.raises(DashboardAccessDeniedError, match="payroll"):
        service.publish_dashboard(record.id, 1, {}, "alice")

    validation.assert_not_called()
    assert connector.calls == []
    assert dao.revisions == []
    assert dao.shares == []


def test_publish_allows_authorized_sources_and_public_reads_do_not_query(
    tmp_path, monkeypatch
):
    """The source guard preserves authorized publication and frozen public reads."""
    # Register the lazily imported vault table before creating the test database.
    from dbgpt_app.openapi.api_v1.dashboard.share_vault import (
        DashboardShareSecretEntity,  # noqa: F401
    )

    monkeypatch.setenv("DBGPT_SHARE_KEY_FILE", str(tmp_path / "share.key"))
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    dao = DashboardDao(manager)
    connector = FakeConnector()
    policy = Mock(return_value=True)
    service = DashboardService(
        dao=dao,
        connector_resolver=lambda _: connector,
        authorization_service=DashboardAuthorizationService(
            dashboard_dao=dao,
            access_dao=DashboardAccessDao(manager),
            audit_dao=DashboardAuditDao(manager),
            data_source_authorizer=policy,
            require_data_source_authorizer=True,
        ),
    )
    record = create_record(service)
    policy.reset_mock()
    connector.calls.clear()
    published = service.publish_dashboard(record.id, 1, {}, "alice")
    policy.assert_any_call("alice", "walmart")
    count = len(connector.calls)
    assert count > 0
    assert service.get_public_snapshot(published.share_token).dashboard_id == record.id
    assert len(connector.calls) == count


@pytest.mark.parametrize("federated", [False, True], ids=["single", "federated"])
@pytest.mark.parametrize("execute_queries", [False, True])
def test_publication_validation_authorizes_unsaved_sources_before_query(
    service_fixture, monkeypatch, federated, execute_queries
):
    """Publication materialization requires query access even without widget runs."""
    from dbgpt_app.openapi.api_v1.dashboard.api import validate_dashboard
    from dbgpt_serve.utils.auth import UserRequest

    service, dao, connector = service_fixture
    record = create_record(service)
    payload = record.schema_payload.model_dump(mode="json", by_alias=True)
    query = payload["widgets"][0]["publication"]["query"]
    if federated:
        query["federation"] = {
            "mode": "union_all",
            "sources": [
                {
                    "alias": alias,
                    "data_source_id": source,
                    "sql": query["sql"],
                    "column_mapping": {
                        field["name"]: field["name"] for field in query["output_fields"]
                    },
                }
                for alias, source in [("allowed", "walmart"), ("restricted", "payroll")]
            ],
        }
        query["sql"] = None
    else:
        query["data_source_id"] = "payroll"
    policy = Mock(side_effect=lambda actor, source: source == "walmart")
    service.authorization = DashboardAuthorizationService(
        dashboard_dao=dao,
        access_dao=Mock(),
        audit_dao=Mock(),
        data_source_authorizer=policy,
        require_data_source_authorizer=True,
    )
    resolver = Mock(return_value=connector)
    monkeypatch.setattr(service.query_executor, "_connector_resolver", resolver)
    connector.calls.clear()

    with pytest.raises(HTTPException) as raised:
        validate_dashboard(
            record.id,
            DashboardValidateRequest(
                schema=DashboardSchemaV1.model_validate(payload),
                execute_queries=execute_queries,
                require_publication_bindings=True,
            ),
            UserRequest(user_id="alice"),
            service,
        )

    assert raised.value.status_code == 403
    assert "payroll" in raised.value.detail
    policy.assert_any_call("alice", "payroll")
    resolver.assert_not_called()
    assert connector.calls == []
