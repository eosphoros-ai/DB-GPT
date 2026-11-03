import io
import time
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from dbgpt_serve.financial_analysis.service import FinancialAnalysisService

from .fixtures import extracted


@pytest.fixture
def isolated_service(tmp_path, request):
    engine = create_engine(
        "sqlite:///" + (tmp_path / "comparison.db").as_posix(),
        connect_args={"check_same_thread": False},
    )
    if getattr(request, "param", None) == "legacy":
        from dbgpt_serve.financial_analysis.models import FinancialExportEntity

        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE dbgpt_financial_analysis_run "
                    "(id VARCHAR(36) PRIMARY KEY, owner_id VARCHAR(255) NOT NULL, "
                    "session_id VARCHAR(255) NOT NULL, file_id VARCHAR(64) NOT NULL, "
                    "status VARCHAR(16) NOT NULL, stage VARCHAR(32) NOT NULL, "
                    "created_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, "
                    "completed_at VARCHAR(40), error TEXT, report_json TEXT)"
                )
            )
        FinancialExportEntity.__table__.create(engine)
    factory = sessionmaker(bind=engine)

    @contextmanager
    def session(commit=True):
        with factory() as db_session:
            yield db_session
            if commit:
                db_session.commit()

    payloads = {
        "a": extracted(token="a"),
        "b": extracted("合成乙股份有限公司", token="b"),
        "c": extracted("合成丙股份有限公司", token="c"),
    }
    calls = []

    def get_file(*, owner_id, session_id, file_id):
        if (owner_id, session_id) != ("alice", "scope") or file_id not in payloads:
            return None
        return SimpleNamespace(
            file_id=file_id,
            display_name=file_id + ".pdf",
            media_type="application/pdf",
            sha256=payloads[file_id]["document"]["sha256"],
            size_bytes=32,
        )

    def open_download(**kwargs):
        record = get_file(**kwargs)
        if record:
            return io.BytesIO(("%PDF synthetic " + record.file_id).encode()), record

    @contextmanager
    def materialize(scope, stream, suffix):
        path = tmp_path / (str(time.monotonic_ns()) + suffix)
        path.write_bytes(stream.read())
        try:
            yield path
        finally:
            path.unlink(missing_ok=True)

    def extract(path):
        file_id = path.read_text().rsplit(" ", 1)[1]
        calls.append(file_id)
        value = payloads[file_id]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    registry = SimpleNamespace(
        dao=SimpleNamespace(session=session),
        get_file=get_file,
        open_download=open_download,
        materialize_local_file=materialize,
    )
    service = FinancialAnalysisService(registry, extractor=extract)
    yield service, payloads, calls, engine
    service.close()
    engine.dispose()


def wait_ready(service, run_id):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        state = service.get("alice", "scope", run_id)
        if state["status"] not in {"pending", "running"}:
            return state
        time.sleep(0.01)
    raise AssertionError("Isolated run did not finish")
