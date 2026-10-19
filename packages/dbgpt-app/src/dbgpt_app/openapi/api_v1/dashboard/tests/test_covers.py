import pytest

from dbgpt_app.openapi.api_v1.dashboard.covers import (
    CoverService,
    DashboardCoverEntity,
    DashboardCoverRequest,
)
from dbgpt_app.openapi.api_v1.dashboard.models import (
    DashboardConflictError,
    DashboardNotFoundError,
)

from .test_feedback import real_service as _real_service_fixture

PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA"
    "EAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3x"
    "8AAAAASUVORK5CYII="
)


real_service = _real_service_fixture


def test_cover_is_private_and_does_not_create_versions(real_service):
    service, record, _ = real_service
    covers = CoverService(service)
    assert not covers.read(record.id, "alice")["available"]
    for _ in range(3):
        covers.save(
            record.id, "alice", DashboardCoverRequest(expected_revision=1, image=PNG)
        )
    image = covers.read(record.id, "alice")
    assert image["image"] == PNG and not image["stale"]
    with service.dao.session(commit=False) as session:
        assert session.query(DashboardCoverEntity).count() == 1
    assert service.get_dashboard(record.id, "alice").current_revision == 1
    assert len(service.list_edit_versions(record.id, "alice")) == 1
    with pytest.raises(DashboardNotFoundError):
        covers.read(record.id, "bob")


def test_old_cover_stays_visible_but_cannot_overwrite_new_revision(real_service):
    service, record, _ = real_service
    covers = CoverService(service)
    covers.save(
        record.id, "alice", DashboardCoverRequest(expected_revision=1, image=PNG)
    )
    schema = record.schema_payload.model_copy(deep=True)
    schema.dashboard.title = "Changed"
    service.update_dashboard(record.id, schema, 1, "alice")
    assert covers.read(record.id, "alice")["stale"]
    with pytest.raises(DashboardConflictError):
        covers.save(
            record.id, "alice", DashboardCoverRequest(expected_revision=1, image=PNG)
        )


@pytest.mark.parametrize(
    "image", ["data:image/svg+xml," + "x" * 80, "data:image/png;base64," + "x" * 100]
)
def test_cover_rejects_non_png_payload(real_service, image):
    service, record, _ = real_service
    with pytest.raises(ValueError):
        CoverService(service).save(
            record.id, "alice", DashboardCoverRequest(expected_revision=1, image=image)
        )
