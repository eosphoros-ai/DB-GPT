"""SQLite contract tests for the session file DAO."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError, asdict

import pytest
from pydantic import BaseModel

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file import domain
from dbgpt_serve.session_file.domain import FileScope, SessionFileStatus
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity


@pytest.fixture(autouse=True)
def setup_database():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


@pytest.fixture
def dao() -> SessionFileDao:
    return SessionFileDao()


def _file_request(file_id: str, ordinal: int = 0, **overrides):
    request = {
        "file_id": file_id,
        "owner_id": "alice",
        "session_id": "conv-1",
        "task_id": None,
        "display_name": f"{file_id}.csv",
        "storage_uri": f"file:///managed/{file_id}.csv",
        "media_type": "text/csv",
        "file_kind": "table",
        "size_bytes": 10,
        "sha256": "a" * 64,
        "ordinal": ordinal,
        "status": SessionFileStatus.READY.value,
        "inspection_json": '{"delimiter": ","}',
        "error_code": None,
        "error_message": None,
        "source_file_id": None,
    }
    request.update(overrides)
    return request


@pytest.mark.parametrize(
    ("session_id", "task_id"),
    [(None, None), ("conv-1", "task-1")],
)
def test_create_rejects_invalid_scope_before_flush(dao, session_id, task_id):
    with pytest.raises(ValueError, match="exactly one"):
        dao.create(_file_request("sf_invalid", session_id=session_id, task_id=task_id))

    with dao.session(commit=False) as session:
        assert session.query(SessionFileEntity).count() == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"owner_id": "   "},
        {"session_id": "   "},
        {"session_id": None, "task_id": "   "},
    ],
)
def test_create_rejects_blank_owner_or_selected_scope_before_flush(dao, overrides):
    with pytest.raises(ValueError, match="must not be blank"):
        dao.create(_file_request("sf_blank_scope", **overrides))

    with dao.session(commit=False) as session:
        assert session.query(SessionFileEntity).count() == 0


def test_create_accepts_pydantic_v2_request(dao):
    class FileRequest(BaseModel):
        file_id: str
        owner_id: str
        session_id: str
        task_id: str | None
        display_name: str
        storage_uri: str
        media_type: str
        file_kind: str
        size_bytes: int
        sha256: str
        ordinal: int
        status: str
        inspection_json: str | None
        error_code: str | None
        error_message: str | None
        source_file_id: str | None

    created = dao.create(FileRequest(**_file_request("sf_pydantic")))

    assert created.file_id == "sf_pydantic"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "unknown"),
        ("size_bytes", -1),
        ("ordinal", -1),
        ("sha256", "a" * 63),
        ("sha256", "a" * 65),
        ("sha256", "g" * 64),
    ],
)
def test_create_rejects_invalid_values_before_flush(dao, field, value):
    with pytest.raises(ValueError):
        dao.create(_file_request("sf_invalid_value", **{field: value}))

    with dao.session(commit=False) as session:
        assert session.query(SessionFileEntity).count() == 0


def test_create_preserves_sha256_case(dao):
    sha256 = "Aa" * 32

    dao.create(_file_request("sf_sha_case", sha256=sha256))

    with dao.session(commit=False) as session:
        entity = session.query(SessionFileEntity).one()
        assert entity.sha256 == sha256


def test_create_validates_status_before_opening_a_session(dao, monkeypatch):
    @contextmanager
    def fail_if_opened(*args, **kwargs):
        pytest.fail("database session opened before validation")
        yield

    monkeypatch.setattr(dao, "session", fail_if_opened)

    with pytest.raises(ValueError):
        dao.create(_file_request("sf_invalid_status", status="unknown"))


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("get_one", ({"file_id": "sf_acl"},)),
        ("get_list", ({},)),
        ("get_list_page", ({}, 1, 20)),
        ("update", ({"file_id": "sf_acl"}, {"status": "failed"})),
        ("delete", ({"file_id": "sf_acl"},)),
    ],
)
def test_generic_crud_cannot_bypass_acl(dao, method_name, args):
    dao.create(_file_request("sf_acl"))

    with pytest.raises(NotImplementedError, match="scope"):
        getattr(dao, method_name)(*args)


def test_owner_and_scope_lookup_is_indistinguishable_from_not_found(dao):
    dao.create(_file_request("sf_a"))

    found = dao.get_by_file_id("sf_a", FileScope("alice", session_id="conv-1"))
    wrong_owner = dao.get_by_file_id("sf_a", FileScope("bob", session_id="conv-1"))
    wrong_scope = dao.get_by_file_id("sf_a", FileScope("alice", session_id="conv-2"))
    missing = dao.get_by_file_id("sf_missing", FileScope("alice", session_id="conv-1"))

    assert found is not None
    assert found.file_id == "sf_a"
    assert wrong_owner is None
    assert wrong_scope is None
    assert missing is None


def test_scope_listing_is_ordered_by_ordinal_and_totals_bytes(dao):
    dao.create(_file_request("sf_2", ordinal=2, size_bytes=7))
    dao.create(_file_request("sf_0", ordinal=0, size_bytes=11))
    dao.create(_file_request("sf_1", ordinal=1, size_bytes=13))
    dao.create(
        _file_request("sf_other", owner_id="bob", session_id="conv-1", size_bytes=100)
    )

    scope = FileScope("alice", session_id="conv-1")

    assert [item.file_id for item in dao.list_by_scope(scope)] == [
        "sf_0",
        "sf_1",
        "sf_2",
    ]
    assert dao.total_size_bytes(scope) == 31


def test_total_owner_size_bytes_sums_across_scopes_and_isolates_owners(dao):
    dao.create(_file_request("sf_session", size_bytes=11))
    dao.create(
        _file_request(
            "sf_task",
            session_id=None,
            task_id="task-1",
            size_bytes=13,
        )
    )
    dao.create(_file_request("sf_bob", owner_id="bob", size_bytes=100))

    assert dao.total_owner_size_bytes("alice") == 24
    assert dao.total_owner_size_bytes("bob") == 100
    assert dao.total_owner_size_bytes("missing") == 0


@pytest.mark.parametrize("owner_id", [None, "", "   "])
def test_total_owner_size_bytes_rejects_empty_owner(dao, owner_id):
    with pytest.raises(ValueError, match="owner_id"):
        dao.total_owner_size_bytes(owner_id)


def test_update_status_is_atomic_and_scope_constrained(dao):
    dao.create(_file_request("sf_update"))
    wrong_scope = FileScope("bob", session_id="conv-1")
    scope = FileScope("alice", session_id="conv-1")

    assert dao.update_status("sf_update", wrong_scope, SessionFileStatus.FAILED) is None
    updated = dao.update_status(
        "sf_update",
        scope,
        SessionFileStatus.PREVIEW_FAILED.value,
        inspection_json='{"reason": "invalid csv"}',
        error_code="INVALID_CSV",
        error_message="Invalid CSV content",
    )

    assert updated is not None
    assert updated.status is SessionFileStatus.PREVIEW_FAILED
    with dao.session(commit=False) as session:
        entity = session.query(SessionFileEntity).one()
        assert entity.inspection_json == '{"reason": "invalid csv"}'
        assert entity.error_code == "INVALID_CSV"
        assert entity.error_message == "Invalid CSV content"


def test_update_status_rejects_invalid_status_without_writing(dao):
    dao.create(_file_request("sf_bad_status"))
    scope = FileScope("alice", session_id="conv-1")

    with pytest.raises(ValueError):
        dao.update_status("sf_bad_status", scope, "unknown")

    assert dao.get_by_file_id("sf_bad_status", scope).status is SessionFileStatus.READY


def test_delete_by_file_id_is_atomic_and_scope_constrained(dao):
    dao.create(_file_request("sf_delete"))

    assert not dao.delete_by_file_id("sf_delete", FileScope("bob", session_id="conv-1"))
    assert dao.delete_by_file_id("sf_delete", FileScope("alice", session_id="conv-1"))
    assert not dao.delete_by_file_id(
        "sf_delete", FileScope("alice", session_id="conv-1")
    )


def test_lineage_query_is_owner_and_scope_constrained(dao):
    dao.create(_file_request("sf_child", source_file_id="sf_source"))
    dao.create(
        _file_request(
            "sf_other_owner",
            owner_id="bob",
            source_file_id="sf_source",
        )
    )
    dao.create(
        _file_request(
            "sf_other_scope",
            session_id="conv-2",
            source_file_id="sf_source",
        )
    )

    items = dao.list_by_source_file_id(
        "sf_source", FileScope("alice", session_id="conv-1")
    )

    assert [item.file_id for item in items] == ["sf_child"]
    assert (
        dao.list_by_source_file_id(
            "sf_source", FileScope("alice", session_id="missing")
        )
        == []
    )


def test_private_lookup_returns_frozen_record_not_orm_entity(dao):
    dao.create(_file_request("sf_private"))

    record = dao.get_private_file_by_id(
        "sf_private", FileScope("alice", session_id="conv-1")
    )

    assert isinstance(record, domain.SessionFilePrivateRecord)
    assert not isinstance(record, SessionFileEntity)
    assert record.storage_uri == "file:///managed/sf_private.csv"
    assert record.owner_id == "alice"
    assert record.session_id == "conv-1"
    assert record.task_id is None
    assert record.inspection_json == '{"delimiter": ","}'
    assert record.created_at is not None
    assert record.updated_at is not None
    with pytest.raises(FrozenInstanceError):
        record.status = SessionFileStatus.FAILED


def test_private_lookup_is_owner_and_scope_constrained(dao):
    dao.create(_file_request("sf_private_acl"))

    assert (
        dao.get_private_file_by_id(
            "sf_private_acl", FileScope("bob", session_id="conv-1")
        )
        is None
    )
    assert (
        dao.get_private_file_by_id(
            "sf_private_acl", FileScope("alice", session_id="conv-2")
        )
        is None
    )


def test_public_mappings_are_explicit_and_exclude_private_fields(dao):
    request = _file_request("sf_public", error_code="PRIVATE_ERROR")
    manifest = dao.create(request)
    entity = SessionFileEntity(**request)

    snapshot = dao.to_snapshot(entity)
    expected = {
        "file_id": "sf_public",
        "name": "sf_public.csv",
        "size": 10,
        "media_type": "text/csv",
        "kind": "table",
        "status": SessionFileStatus.READY,
        "ordinal": 0,
    }

    assert asdict(manifest) == expected
    assert asdict(snapshot) == expected
    for private_field in (
        "owner_id",
        "session_id",
        "task_id",
        "storage_uri",
        "sha256",
        "inspection_json",
        "error_code",
        "error_message",
        "source_file_id",
    ):
        assert private_field not in asdict(manifest)
        assert private_field not in asdict(snapshot)
