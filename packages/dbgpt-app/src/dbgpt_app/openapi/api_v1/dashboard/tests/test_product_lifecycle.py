from datetime import datetime

from sqlalchemy import event

from dbgpt.storage.metadata import DatabaseManager, Model
from dbgpt_app.openapi.api_v1.dashboard.access import DashboardAuthorizationService
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardAccessDao,
    DashboardAuditDao,
    DashboardDao,
    DashboardEntity,
)
from dbgpt_app.openapi.api_v1.dashboard.schemas import (
    DashboardCopyRequest,
    DashboardCreateRequest,
    DashboardSchemaV1,
    DashboardStatus,
)
from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService

from .test_service import FakeConnector, schema_payload


def _runtime(*, authorization: bool = False):
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:", base=Model)
    Model.metadata.create_all(manager.engine)
    dao = DashboardDao(manager)
    authorization_service = None
    if authorization:
        authorization_service = DashboardAuthorizationService(
            dashboard_dao=dao,
            access_dao=DashboardAccessDao(manager),
            audit_dao=DashboardAuditDao(manager),
        )
    service = DashboardService(
        dao=dao,
        authorization_service=authorization_service,
        connector_resolver=lambda _: FakeConnector(),
    )
    return manager, dao, service


def _create(service: DashboardService):
    return service.create_dashboard(
        DashboardCreateRequest(
            schema=DashboardSchemaV1.model_validate(schema_payload())
        ),
        "alice",
    )


def test_archive_restore_copy_and_published_revision_restore():
    _, _, service = _runtime()
    created = _create(service)

    archived = service.set_archived(
        created.id, created.current_revision, "alice", archived=True
    )
    assert archived.status == DashboardStatus.ARCHIVED
    restored = service.set_archived(
        created.id, archived.current_revision, "alice", archived=False
    )
    assert restored.status == DashboardStatus.DRAFT

    copied = service.copy_dashboard(
        created.id, DashboardCopyRequest(title="Retail sales copy"), "alice"
    )
    assert copied.id != created.id
    assert copied.schema_payload.dashboard.title == "Retail sales copy"
    assert copied.status == DashboardStatus.DRAFT

    published = service.publish_dashboard(
        created.id, restored.current_revision, {}, "alice"
    )
    changed_schema = service.get_dashboard(created.id, "alice").schema_payload
    changed_schema.dashboard.title = "Temporary title"
    changed = service.update_dashboard(
        created.id, changed_schema, restored.current_revision, "alice"
    )
    restored_revision = service.restore_revision(
        created.id,
        published.published_revision,
        changed.current_revision,
        "alice",
    )
    assert restored_revision.schema_payload.dashboard.title == "Retail sales"
    assert restored_revision.current_revision == changed.current_revision + 1
    assert service.list_revisions(created.id, "alice")[0].published_revision == 1


def test_500_dashboard_page_uses_two_queries_and_supports_search():
    manager, dao, service = _runtime(authorization=True)
    now = datetime.now()
    template = DashboardSchemaV1.model_validate(schema_payload())
    with dao.session() as session:
        session.add_all(
            [
                DashboardEntity(
                    id=f"dashboard-{index:03d}",
                    owner_id="alice",
                    title=f"Retail dashboard {index:03d}",
                    description="Retail operations",
                    data_source_id="walmart",
                    schema_json=service._serialize_schema(template),
                    current_revision=1,
                    status="draft" if index != 499 else "archived",
                    gmt_created=now,
                    gmt_modified=now,
                )
                for index in range(500)
            ]
        )

    statements = []

    def track(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(manager.engine, "before_cursor_execute", track)
    try:
        page = service.list_dashboard_page("alice", limit=24, offset=0)
    finally:
        event.remove(manager.engine, "before_cursor_execute", track)

    assert page.total == 499
    assert len(page.items) == 24
    assert len(statements) == 2

    match = service.list_dashboard_page(
        "alice", search="dashboard 042", limit=24, offset=0
    )
    assert match.total == 1
    assert match.items[0].id == "dashboard-042"
    archived = service.list_dashboard_page(
        "alice", status=DashboardStatus.ARCHIVED, limit=24, offset=0
    )
    assert archived.total == 1
    assert archived.items[0].id == "dashboard-499"
    all_dashboards = service.list_dashboard_page(
        "alice", include_archived=True, limit=24, offset=0
    )
    assert all_dashboards.total == 500
    assert len(service.list_dashboards("alice")) == 499
    assert len(service.list_dashboards("alice", include_archived=True)) == 500
